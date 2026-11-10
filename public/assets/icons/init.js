/**
 * Service Desk Hub - Lucide Icons
 * Local icon initialization
 */
(function () {
  function initIcons(root = document) {
    if (window.lucide) {
      window.lucide.createIcons({
        root,
        attrs: {
          'stroke-width': 1.8,
          'stroke-linecap': 'round',
          'stroke-linejoin': 'round'
        }
      });
    }
  }

  window.initHubIcons = initIcons;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => initIcons());
  } else {
    initIcons();
  }
})();
