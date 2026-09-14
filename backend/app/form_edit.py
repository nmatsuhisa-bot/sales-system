# -*- coding: utf-8 -*-
"""帳票編集モード（帳票画面の上で直接編集する仕組み）

各帳票の HTML は mode で表示を切り替える。
  - "pdf"  : PDF出力用。値はプレーンテキスト
  - "view" : 印刷プレビュー。値はプレーンテキスト
  - "edit" : 帳票画面での編集。値の欄を contenteditable にし、上部に保存バーを出す

値の欄には data-k="キー" を付ける。キーはドット区切りで入れ子を表す。
  例: site_name / spec_json.motor_kw / items_json.0.machine
画面の JS がすべての data-k を集めて保存APIへ送り、サーバ側で unflatten して保存する。
"""
import html as _h
import json
import re
from datetime import date, datetime


def ef(mode: str, key: str, value, block: bool = False, placeholder: str = "") -> str:
    """値の欄。編集モードなら編集可能な要素、それ以外はエスケープしたテキストを返す。

    block=True は複数行（除外事項・備考など）。改行を保つ。
    """
    v = "" if value is None else str(value)
    if mode != "edit":
        t = _h.escape(v)
        return t.replace("\n", "<br>") if block else t
    tag = "div" if block else "span"
    ph = (' data-ph="%s"' % _h.escape(placeholder)) if placeholder else ""
    return '<%s class="ef%s" contenteditable="true" data-k="%s"%s>%s</%s>' % (
        tag, " ef-block" if block else "", _h.escape(key), ph, _h.escape(v), tag)


def eftoggle(mode: str, key: str, value: str, options=("有", "無", "")) -> str:
    """クリックで選択肢を切り替える欄（有/無、未/済 など）。編集モード以外は太字下線で強調表示。"""
    v = value or ""
    if mode != "edit":
        return _h.escape(v)
    return '<span class="ef ef-toggle" data-k="%s" data-toggle="%s" title="クリックで切替">%s</span>' % (
        _h.escape(key), _h.escape(",".join(options)), _h.escape(v) or "　")


EDIT_CSS = """
.ef{border-bottom:1px dashed #2563eb;min-width:2.5em;display:inline-block;padding:0 2px;
    outline:none;cursor:text;background:rgba(37,99,235,.04);white-space:pre-wrap}
.ef-block{display:block;min-height:1.6em}
.ef:empty:before{content:attr(data-ph);color:#9ca3af}
.ef:hover{background:rgba(37,99,235,.10)}
.ef:focus{background:#fff9c4;border-bottom:1px solid #2563eb}
.ef-toggle{cursor:pointer;user-select:none;border:1px dashed #2563eb;border-radius:3px;
    padding:0 6px;text-align:center}
.ef-bar{position:sticky;top:0;z-index:50;background:#1e3a5f;color:#fff;padding:8px 12px;
    display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 12px;border-radius:6px;
    font-family:'Hiragino Sans','Yu Gothic',sans-serif;font-size:12px}
.ef-bar button,.ef-bar select{border:none;border-radius:5px;padding:6px 12px;cursor:pointer;font-size:12px}
.ef-bar .p{background:#16a34a;color:#fff}.ef-bar .s{background:#2563eb;color:#fff}
.ef-bar .g{background:#e5e7eb;color:#111}.ef-bar .w{background:#f59e0b;color:#111}
.ef-bar .msg{margin-left:auto;font-weight:bold}
.ef-note{background:#fef3c7;border:1px solid #f59e0b;color:#92400e;padding:6px 10px;
    border-radius:5px;margin:0 0 10px;font-size:11px}
.ef-rowop{font-size:10px;margin:2px 0 8px}
.ef-rowop button{border:1px solid #dc2626;color:#dc2626;background:#fff;border-radius:4px;
    padding:1px 8px;cursor:pointer}
@media print{.ef-bar,.ef-note,.ef-rowop,.no-print{display:none!important}
    .ef,.ef-toggle{border:none!important;background:none!important}
    .ef:empty:before{content:""}}
"""

# 帳票画面の JS。__CFG__ をサーバ側で置換する
EDIT_JS = r"""
(function(){
  var CFG = __CFG__;
  var dirty = false;
  function msg(t, ok){ var m=document.getElementById('ef-msg'); if(!m) return;
    m.textContent=t; m.style.color= ok===false ? '#fca5a5' : '#bbf7d0';
    if(ok!==false) setTimeout(function(){ if(m.textContent===t) m.textContent=''; }, 3000); }
  function collect(){
    var o = {};
    document.querySelectorAll('[data-k]').forEach(function(el){
      o[el.getAttribute('data-k')] = el.innerText.replace(/ /g,' ').replace(/\s+$/,'').replace(/^\s+/,'');
    });
    return o;
  }
  async function save(op){
    var body = {fields: collect()};
    if(op) body.op = op;
    msg('保存中...');
    try{
      var r = await fetch(CFG.save_url, {method:'POST', headers:{'Content-Type':'application/json'},
                                          body: JSON.stringify(body)});
      if(!r.ok){
        var t = ''; try{ var j = await r.json(); t = j.detail || JSON.stringify(j); }catch(e){ t = r.statusText; }
        msg('保存できません: ' + t, false); alert('保存できませんでした。\n' + t); return false;
      }
      dirty = false; msg('保存しました'); return true;
    }catch(e){ msg('通信エラー', false); alert('通信エラーで保存できませんでした'); return false; }
  }
  window.efSave = function(){ return save(); };
  window.efPdf  = async function(){ if(await save()) window.open(CFG.pdf_url, '_blank'); };
  window.efPdf2 = async function(u){ if(await save()) window.open(u, '_blank'); };
  window.efOp   = async function(op){ if(await save(op)) { dirty=false; location.reload(); } };
  window.efDelRow = function(i){ if(confirm((i+1)+'件目の明細を削除します。よろしいですか？')) efOp({del_row:i}); };

  // 業者マスタから選択（該当する帳票のみ）
  window.efVendor = function(sel){
    var v = CFG.vendors && CFG.vendors[sel.value]; if(!v) return;
    Object.keys(CFG.vendor_map||{}).forEach(function(k){
      var el = document.querySelector('[data-k="'+k+'"]'); if(el){ el.innerText = v[CFG.vendor_map[k]] || ''; }
    });
    dirty = true; sel.selectedIndex = 0; msg('業者を反映しました（未保存）');
  };

  // 同じ項目が帳票内に複数回出る場合（件名など）、1か所を直したら他も揃える。
  // 揃えないと保存時に書き換えていない方の値で上書きされてしまう
  document.addEventListener('input', function(e){
    var el = e.target.closest && e.target.closest('[data-k]'); if(!el) return;
    dirty = true;
    var k = el.getAttribute('data-k');
    document.querySelectorAll('[data-k]').forEach(function(o){
      if(o !== el && o.getAttribute('data-k') === k && !o.hasAttribute('data-toggle')) o.innerText = el.innerText;
    });
  });
  document.querySelectorAll('[data-toggle]').forEach(function(el){
    el.addEventListener('click', function(){
      var o = el.getAttribute('data-toggle').split(',');
      var cur = el.innerText.trim(); if(cur==='　') cur='';
      var i = (o.indexOf(cur) + 1) % o.length; el.innerText = o[i] || '　'; dirty = true;
    });
  });
  // 1行の欄では Enter で改行させない（帳票の枠が崩れるため）
  document.addEventListener('keydown', function(e){
    var el = e.target;
    if(e.key==='Enter' && el.classList && el.classList.contains('ef') && !el.classList.contains('ef-block')){
      e.preventDefault(); el.blur();
    }
    if((e.ctrlKey||e.metaKey) && e.key==='s'){ e.preventDefault(); save(); }
  });
  // 貼り付けは書式を捨ててテキストのみ（Excel等からの貼り付けで枠が崩れるのを防ぐ）
  document.addEventListener('paste', function(e){
    var el = e.target.closest && e.target.closest('.ef'); if(!el) return;
    e.preventDefault();
    var t = (e.clipboardData||window.clipboardData).getData('text');
    if(!el.classList.contains('ef-block')) t = t.replace(/[\r\n]+/g,' ');
    document.execCommand('insertText', false, t);
  });
  window.addEventListener('beforeunload', function(e){ if(dirty){ e.preventDefault(); e.returnValue=''; } });
})();
"""


def edit_bar(title: str, pdf_url: str, extra_buttons: str = "", notes=None,
             vendors=None, vendor_map=None, pdf_label: str = "保存してPDF") -> str:
    """帳票画面の上部に出す保存バー"""
    vsel = ""
    if vendors:
        opts = "".join('<option value="%d">%s</option>' % (i, _h.escape(
            (v.get("name") or "") + ((" " + v["branch"]) if v.get("branch") else "")))
            for i, v in enumerate(vendors))
        vsel = ('<select onchange="efVendor(this)" class="g">'
                '<option value="">業者マスタから選択…</option>%s</select>' % opts)
    note_html = "".join('<div class="ef-note">%s</div>' % n for n in (notes or []))
    return (
        '<div class="ef-bar">'
        '<b style="margin-right:6px">%s（編集中）</b>'
        '<button class="s" onclick="efSave()">保存</button>'
        '<button class="p" onclick="efPdf()">%s</button>'
        '%s%s'
        '<button class="g" onclick="window.print()">印刷</button>'
        '<span class="msg" id="ef-msg"></span>'
        '</div>%s'
        '<div class="ef-note">青い下線の箇所をクリックすると、その場で書き換えられます。'
        '有/無などの枠はクリックで切り替わります。保存は Ctrl+S でも可能です。</div>'
    ) % (_h.escape(title), _h.escape(pdf_label), extra_buttons, vsel, note_html)


def inject_edit(html: str, *, title: str, save_url: str, pdf_url: str,
                extra_buttons: str = "", notes=None, vendors=None, vendor_map=None,
                pdf_label: str = "保存してPDF") -> str:
    """組み立て済みの帳票HTMLに、編集用のCSS・保存バー・JSを差し込む"""
    cfg = {"save_url": save_url, "pdf_url": pdf_url,
           "vendors": vendors or [], "vendor_map": vendor_map or {}}
    js = EDIT_JS.replace("__CFG__", json.dumps(cfg, ensure_ascii=False))
    bar = edit_bar(title, pdf_url, extra_buttons, notes, vendors, vendor_map, pdf_label)
    html = html.replace("</head>", "<style>%s</style></head>" % EDIT_CSS, 1)
    html = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + bar, html, count=1)
    html = html.replace("</body>", "<script>%s</script></body>" % js, 1)
    return html


# ------------------------------------------------------------------
# 保存データの組み立て
# ------------------------------------------------------------------
def strip_first_no_print(html: str) -> str:
    """最初の class="no-print" の div を、入れ子を数えて丸ごと取り除く。

    元の帳票が持つ「PDF印刷」ボタン帯。編集画面では保存バーと重複するため出さない。
    """
    m = re.search(r'<div[^>]*class="no-print"[^>]*>', html)
    if not m:
        return html
    depth, start = 1, m.end()
    for t in re.finditer(r"<div\b|</div>", html[start:]):
        depth += 1 if t.group(0).startswith("<div") else -1
        if depth == 0:
            return html[:m.start()] + html[start + t.end():]
    return html


def get_path(d, key, default=""):
    """ドット区切りのキーで入れ子の値を取り出す（items_json.0.machine 等）"""
    cur = d
    for p in key.split("."):
        if isinstance(cur, list):
            try:
                cur = cur[int(p)]
            except (ValueError, IndexError):
                return default
        elif isinstance(cur, dict):
            if p not in cur:
                return default
            cur = cur[p]
        else:
            return default
    return default if cur is None else cur


def apply_fields(base: dict, fields: dict) -> dict:
    """画面から来たドット区切りの値を、既存データへ上書きマージする。

    画面に出ていない項目は既存の値を保つ（帳票に表示しない内部項目を消さないため）。
    """
    out = json.loads(json.dumps(base or {}, default=str))
    for key, val in (fields or {}).items():
        parts = key.split(".")
        cur = out
        for i, p in enumerate(parts):
            last = i == len(parts) - 1
            nxt_idx = (not last) and parts[i + 1].isdigit()
            if isinstance(cur, list):
                idx = int(p)
                while len(cur) <= idx:
                    cur.append([] if nxt_idx else {})
                if last:
                    cur[idx] = val
                else:
                    if not isinstance(cur[idx], (dict, list)):
                        cur[idx] = [] if nxt_idx else {}
                    cur = cur[idx]
            else:
                if last:
                    cur[p] = val
                else:
                    if not isinstance(cur.get(p), (dict, list)):
                        cur[p] = [] if nxt_idx else {}
                    cur = cur[p]
    return out


def apply_row_op(data: dict, op, list_key: str = "items_json"):
    """明細の行追加・削除"""
    if not op:
        return data
    rows = list(data.get(list_key) or [])
    if op.get("add_row"):
        rows.append({})
    if op.get("del_row") is not None:
        i = int(op["del_row"])
        if 0 <= i < len(rows):
            rows.pop(i)
    data[list_key] = rows
    return data


_DATE_PATTERNS = (
    (re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$"), None),
    (re.compile(r"^\s*(\d{4})/(\d{1,2})/(\d{1,2})\s*$"), None),
    (re.compile(r"^\s*(\d{4})\.(\d{1,2})\.(\d{1,2})\s*$"), None),
    (re.compile(r"^\s*(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日"), None),
)


def parse_date(v, label: str):
    """帳票画面で手入力された日付を解釈する。解釈できなければ項目名つきで知らせる。"""
    if v in (None, ""):
        return None
    if isinstance(v, (date, datetime)):
        return v if isinstance(v, date) else v.date()
    s = str(v).strip()
    if s in ("", "　"):
        return None
    for rx, _ in _DATE_PATTERNS:
        m = rx.match(s)
        if m:
            try:
                return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            except ValueError:
                break
    raise ValueError("「%s」の日付「%s」を読み取れません。2026-09-07 や 2026/9/7 の形で入力してください" % (label, s))
