(function () {
  var t = localStorage.getItem("af-theme");
  document.documentElement.setAttribute("data-theme", t || "dark");
})();
