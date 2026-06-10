// cashflow.js - UI del Reporte de Flujo de Caja

import { getBase } from './data_service.js';

export function render(container) {
  const base = getBase();
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = `
    <h2>Reporte Flujo de Caja</h2>
    <p>${base ? `Base cargada: ${base.name}` : 'Aún no se ha cargado ninguna base.'}</p>
    <button id="gen-cashflow">Generar Flujo de Caja</button>
    <div id="cashflow-result" style="margin-top:0.5rem;"></div>
  `;
  container.appendChild(card);

  const btn = card.querySelector('#gen-cashflow');
  const resultDiv = card.querySelector('#cashflow-result');
  btn.addEventListener('click', () => {
    if (!base) {
      resultDiv.textContent = 'Primero carga la base de datos.';
      return;
    }
    resultDiv.textContent = 'Calculando flujo de caja...';
    setTimeout(() => {
      resultDiv.textContent = 'Flujo de caja generado (ejemplo).';
    }, 1000);
  });
}
