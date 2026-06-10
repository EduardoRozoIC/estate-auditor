const BASE_URL = '/api';

const api = {
  uploadBaseExcel: async (file) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const resp = await fetch(`${BASE_URL}/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Error al subir el archivo');
    }
    return resp.json();
  },

  runValidation: async (proyecto, fecha_datos) => {
    const resp = await fetch(`${BASE_URL}/validate/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ proyecto, fecha_datos }),
    });
    if (!resp.ok) {
      const err = await resp.json();
      throw new Error(err.detail || 'Error al validar');
    }
    return resp.json();
  }
};

export default api;
