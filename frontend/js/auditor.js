// auditor.js - UI del módulo de auditoría (mantiene lógica existente)

import { getBase } from './data_service.js';

export async function render(container) {
  const base = getBase();
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = `
    <h2>Auditoría</h2>
    <p>${base ? `Base cargada: ${base.name}` : 'Aún no se ha cargado ninguna base.'}</p>
    <button id="run-audit">Ejecutar Auditoría</button>
    <div id="audit-result" style="margin-top:0.5rem;"></div>
  `;
  container.appendChild(card);

  const btn = card.querySelector('#run-audit');
  const resultDiv = card.querySelector('#audit-result');
  btn.addEventListener('click', async () => {
    if (!base) {
      resultDiv.textContent = 'Primero carga la base de datos.';
      return;
    }
    // Para demo, simulamos una auditoría simple.
    resultDiv.textContent = 'Ejecutando auditoría...';
    setTimeout(() => {
      resultDiv.textContent = 'Auditoría completada. (Resultado de ejemplo)';
    }, 1000);
  });
}
