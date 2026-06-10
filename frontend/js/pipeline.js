// pipeline.js - UI del Simulador Pipeline

import { getBase } from './data_service.js';

export function render(container) {
  const base = getBase();
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = `
    <h2>Simulador Pipeline de Proyectos</h2>
    <p>${base ? `Base cargada: ${base.name}` : 'Aún no se ha cargado ninguna base.'}</p>
    <button id="run-sim">Ejecutar Simulación</button>
    <div id="sim-result" style="margin-top:0.5rem;"></div>
  `;
  container.appendChild(card);

  const btn = card.querySelector('#run-sim');
  const resultDiv = card.querySelector('#sim-result');
  btn.addEventListener('click', () => {
    if (!base) {
      resultDiv.textContent = 'Primero carga la base de datos.';
      return;
    }
    resultDiv.textContent = 'Simulando pipeline...';
    setTimeout(() => {
      resultDiv.textContent = 'Simulación completada (ejemplo).';
    }, 1500);
  });
}
