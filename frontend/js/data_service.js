// data_service.js - Servicio compartido para la base de datos

let baseData = null;

export function setBase(data) {
  baseData = data;
  // Guardar en localStorage para persistencia entre sesiones
  try {
    localStorage.setItem('estateBase', JSON.stringify(data));
  } catch (e) {
    console.warn('LocalStorage no disponible', e);
  }
}

export function getBase() {
  if (baseData) return baseData;
  // Intentar recuperar de localStorage
  try {
    const stored = localStorage.getItem('estateBase');
    if (stored) {
      baseData = JSON.parse(stored);
    }
  } catch (e) {
    console.warn('Error leyendo de localStorage', e);
  }
  return baseData;
}

export function clearBase() {
  baseData = null;
  try { localStorage.removeItem('estateBase'); } catch (_) {}
}

let pollingInterval = null;

export function pollBase() {
  if (pollingInterval) return; // Already polling

  pollingInterval = setInterval(async () => {
    try {
      const response = await fetch('http://localhost:5000/api/get_base');
      if (response.ok) {
        const currentData = await response.json();
        
        // Check if there is data and if it has changed
        if (currentData.name && (!baseData || currentData.name !== baseData.name)) {
          setBase(currentData);
          // Dispatch event so other parts of the app can react
          const event = new CustomEvent('baseUpdated', { detail: currentData });
          document.dispatchEvent(event);
        }
      }
    } catch (e) {
      console.warn('Error polling base data:', e);
    }
  }, 5000); // Poll every 5 seconds
}

// Automatically start polling when this module is loaded
pollBase();

// Listen for global event to update if other modules use it directly
document.addEventListener('baseLoaded', (e) => {
  setBase(e.detail);
});
