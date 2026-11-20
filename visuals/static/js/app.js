(function () {
  function pad(n) { return String(n).padStart(2, "0"); }
  function tick() {
    var el = document.getElementById("live-clock");
    if (!el) return;
    var d = new Date();
    var text =
      pad(d.getDate()) + "." + pad(d.getMonth() + 1) + "." + d.getFullYear() +
      " " + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
    var span = el.querySelector("span");
    if (span) span.textContent = text;
    else el.textContent = text;
  }
  tick();
  setInterval(tick, 1000);

  window.mtsBindContractDates = function () {
    var start = document.getElementById("sozlesme_baslangic_tarihi");
    var duration = document.getElementById("sozlesme_suresi");
    var end = document.getElementById("sozlesme_bitis_tarihi");
    if (!start || !duration || !end) return;
    function sync() {
      if (!start.value) return;
      var years = parseInt((duration.value || "1").replace(/\D/g, ""), 10) || 1;
      var dt = new Date(start.value + "T00:00:00");
      dt.setFullYear(dt.getFullYear() + years);
      end.value = dt.toISOString().slice(0, 10);
    }
    start.addEventListener("change", sync);
    duration.addEventListener("change", sync);
  };
})();
