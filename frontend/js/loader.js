// loader.js - UI para cargar la base de datos

export function render(container) {
  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = `
    <h2>Cargar Base de Datos</h2>
    <p>Selecciona el archivo Excel/CSV que contiene la información de los inmuebles.</p>
    <input type="file" id="base-file" accept=".xlsx,.csv" />
    <button id="load-btn">Cargar</button>
    <div id="status" style="margin-top:0.5rem;"></div>
  `;
  container.appendChild(card);

  const fileInput = card.querySelector('#base-file');
  const loadBtn = card.querySelector('#load-btn');
  const statusDiv = card.querySelector('#status');

  loadBtn.addEventListener('click', async () => {
    if (!fileInput.files.length) {
      statusDiv.textContent = 'Por favor selecciona un archivo.';
      return;
    }
    const file = fileInput.files[0];
    statusDiv.textContent = 'Cargando...';
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch('http://localhost:5000/api/upload_base', {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const baseData = await response.json();
      
      // Update data service with the API response
      import('./data_service.js').then(ds => {
        ds.setBase(baseData);
        statusDiv.textContent = `Base "${baseData.name}" cargada exitosamente.`;
      });

    } catch (err) {
      console.error('Error uploading file:', err);
      statusDiv.textContent = 'Error al cargar el archivo. Asegúrate de que el servidor esté corriendo.';
    }
  });
}
