/* 支付前确认接进聊天：
   在消息真正发给 A1 之前，先用确定性规则核一遍；命中就当场插一张"先停一下"卡。
   不改 app.js：只包一层它已经用的 api()，对原流程透明。 */
(function () {
  if (typeof api !== 'function') return;

  var originalApi = api;

  function esc(value) {
    var box = document.createElement('div');
    box.textContent = value == null ? '' : value;
    return box.innerHTML;
  }

  function plainText(data) {
    var lines = [data.headline].concat(data.pauseSteps || []);
    (data.channels || []).forEach(function (c) { lines.push(c.name + '：' + c.note); });
    lines.push('未执行任何转账、支付或汇款；未联系银行、家属或警方；不承诺能追回。');
    return lines.join('\n');
  }

  function card(data) {
    var wrap = document.createElement('article');
    wrap.className = 'message assistant guard-card';
    wrap.innerHTML =
      '<div class="message-body"><div class="bubble">' +
      '<h3 style="margin:0 0 8px;font-size:17px">' + esc(data.headline) + '</h3>' +
      '<p style="font-size:13px;color:#8a5a3c;margin:0 0 10px">命中的要求：' +
      esc((data.matched || []).join('、')) + '</p>' +
      '<p style="font-size:13px;color:#445464;margin:0 0 6px"><b>现在这么做</b></p>' +
      '<ol style="margin:0 0 10px 18px;font-size:14px;line-height:1.8">' +
      (data.pauseSteps || []).map(function (s) { return '<li>' + esc(s) + '</li>'; }).join('') +
      '</ol>' +
      '<p style="font-size:12.5px;color:#8a6a4a;background:#fdf9f4;border:1px dashed #ddc4a8;' +
      'border-radius:8px;padding:8px 10px;margin:0 0 10px;line-height:1.7">' +
      '未执行任何转账、支付或汇款 · 未联系银行、家属或警方 · 不承诺能追回</p>' +
      '<div class="guard-actions" style="display:flex;gap:8px;flex-wrap:wrap">' +
      '<button type="button" data-guard="copy">复制要说的内容</button>' +
      '<button type="button" data-guard="close">我知道了</button>' +
      '</div>' +
      '<p style="font-size:12px;color:#93a1b0;margin:8px 0 0">' + esc(data.note) + '</p>' +
      '</div></div>';

    wrap.querySelector('[data-guard="copy"]').onclick = function () {
      var say = function () { status('已复制，可以发给家里人。'); };
      if (navigator.clipboard) navigator.clipboard.writeText(plainText(data)).then(say, say);
      else say();
    };
    wrap.querySelector('[data-guard="close"]').onclick = function () { wrap.remove(); };
    return wrap;
  }

  var wrapper = function (path, body) {
    if (path === 'message' && body && typeof body.text === 'string' && body.text.trim()) {
      fetch('/api/payment-guard', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: body.text })
      }).then(function (r) { return r.json(); }).then(function (data) {
        if (!data || !data.triggered) return;
        var list = document.getElementById('conversation');
        if (!list) return;
        list.appendChild(card(data));
        list.scrollTop = list.scrollHeight;
        status('这条消息里有"先付钱"或"要验证码"的要求，已先给你一张核对卡。');
      }).catch(function () { /* 规则核对失败不影响正常对话 */ });
    }
    return originalApi.apply(null, arguments);
  };

  api = wrapper;
  window.api = wrapper;
})();
