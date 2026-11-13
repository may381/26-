/* 等待反馈：旅游咨询经常要几十秒（模型排队时更久）。
   在等的时候把状态栏变成"在做什么 + 已经等了多久"，避免用户以为卡死。
   仍然只是包一层 api()，不改 app.js。 */
(function () {
  if (typeof api !== 'function') return;

  var inner = api;
  var timers = {};

  function start(body) {
    var topic = (body && body.topic) || 'auto';
    var text = topic === 'tourism' ? '正在查询真实地点与交通，首次可能要 1 分钟以上；请不要重复点击。'
             : topic === 'fraud' ? '正在核对，受理后会出现结果卡；通常几秒，模型排队时会久一些。'
             : '正在理解你的需求，请稍等…';
    var begin = Date.now();
    status(text);
    clearInterval(timers.id);
    timers.id = setInterval(function () {
      var seconds = Math.round((Date.now() - begin) / 1000);
      if (seconds >= 5) status(text + '（已等 ' + seconds + ' 秒）');
    }, 1000);
    return function stop() {
      clearInterval(timers.id);
      timers.id = null;
    };
  }

  api = function (path, body) {
    var stop = null;
    if (path === 'message' && (!body || !body.text || body.text.charAt(0) !== '/')) {
      stop = start(body);
    }
    var settle = function () { if (stop) stop(); };
    var pending;
    try {
      pending = inner.apply(null, arguments);
    } catch (error) {
      settle();
      throw error;
    }
    if (pending && typeof pending.then === 'function') pending.then(settle, settle);
    else settle();
    return pending;
  };

  window.api = api;
})();
