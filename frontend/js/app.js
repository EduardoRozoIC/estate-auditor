// app.js - Enrutador de módulos y carga diferida

const appRoot = document.getElementById('app-root');
const navItems = document.querySelectorAll('.nav-list li');

let currentModule = null;

function clearActive() {
  navItems.forEach(item => item.classList.remove('active'));
}

function loadModule(moduleName) {
  // Remove previous content
  appRoot.innerHTML = '';
  // Dynamically import the module script
  import(`./${moduleName}.js`).then(module => {
    if (module && typeof module.render === 'function') {
      module.render(appRoot);
    }
  }).catch(err => {
    console.error('Error loading module', moduleName, err);
    appRoot.innerHTML = `<div class="card"><h2>Error</h2><p>Unable to load module ${moduleName}.</p></div>`;
  });
}

navItems.forEach(item => {
  item.addEventListener('click', () => {
    const module = item.getAttribute('data-module');
    if (module === currentModule) return;
    clearActive();
    item.classList.add('active');
    currentModule = module;
    loadModule(module);
  });
});

// Cargar módulo predeterminado (loader)
document.querySelector('.nav-list li[data-module="loader"]').click();

// Export for potential testing
export { loadModule };
