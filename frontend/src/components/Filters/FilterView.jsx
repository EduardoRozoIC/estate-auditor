import { useState, useMemo } from 'react';
import { ArrowRight, ArrowLeft, Building2, Calendar } from 'lucide-react';

export default function FilterView({ data, onSubmit, onBack, isLoading }) {
  const [proyecto, setProyecto] = useState(data?.proyectos[0] || '');
  const [fecha, setFecha] = useState('');

  // Fechas disponibles según el proyecto seleccionado
  const fechasDisponibles = useMemo(() => {
    if (!proyecto || !data?.fechas_datos) return [];
    return data.fechas_datos[proyecto] || [];
  }, [proyecto, data]);

  // Autoseleccionar la fecha más reciente si está disponible
  useMemo(() => {
    if (fechasDisponibles.length > 0 && !fechasDisponibles.includes(fecha)) {
      setFecha(fechasDisponibles[fechasDisponibles.length - 1]);
    }
  }, [fechasDisponibles]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (proyecto && fecha) {
      onSubmit(proyecto, fecha);
    }
  };

  return (
    <div style={{maxWidth: '600px', margin: '4rem auto'}}>
      <div className="card">
        <button className="btn btn-secondary" onClick={onBack} style={{marginBottom: '1.5rem', padding: '0.25rem 0.5rem'}}>
          <ArrowLeft size={16} /> Volver
        </button>

        <h2 style={{fontSize: '1.5rem', marginBottom: '1.5rem'}}>Selecciona el Snapshot</h2>
        
        <div style={{display: 'flex', backgroundColor: 'var(--bg-surface-elevated)', padding: '1rem', borderRadius: 'var(--radius-md)', marginBottom: '2rem', gap: '2rem'}}>
          <div>
            <div style={{color: 'var(--text-secondary)', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase'}}>Registros Base</div>
            <div className="mono" style={{fontSize: '1.25rem'}}>{data?.total_registros.toLocaleString()}</div>
          </div>
          <div>
            <div style={{color: 'var(--text-secondary)', fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase'}}>Proyectos</div>
            <div className="mono" style={{fontSize: '1.25rem'}}>{data?.proyectos.length}</div>
          </div>
        </div>

        <form onSubmit={handleSubmit}>
          <div style={{marginBottom: '1.5rem'}}>
            <label style={{display: 'block', marginBottom: '0.5rem', fontWeight: 500}}>
              Proyecto a Auditar
            </label>
            <div style={{position: 'relative'}}>
              <Building2 style={{position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)'}} size={20} />
              <select 
                value={proyecto}
                onChange={(e) => setProyecto(e.target.value)}
                style={{width: '100%', padding: '0.75rem 1rem 0.75rem 2.8rem', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-strong)', color: 'white', borderRadius: 'var(--radius-md)', fontSize: '1rem', appearance: 'none'}}
              >
                {data?.proyectos.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
          </div>

          <div style={{marginBottom: '2rem'}}>
            <label style={{display: 'block', marginBottom: '0.5rem', fontWeight: 500}}>
              Fecha de Corte (Versión)
            </label>
            <div style={{position: 'relative'}}>
              <Calendar style={{position: 'absolute', left: '1rem', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-secondary)'}} size={20} />
              <select 
                value={fecha}
                onChange={(e) => setFecha(e.target.value)}
                style={{width: '100%', padding: '0.75rem 1rem 0.75rem 2.8rem', backgroundColor: 'var(--bg-app)', border: '1px solid var(--border-strong)', color: 'white', borderRadius: 'var(--radius-md)', fontSize: '1rem', appearance: 'none'}}
              >
                {fechasDisponibles.length === 0 && <option value="">Sin fechas disponibles</option>}
                {fechasDisponibles.map(f => (
                  <option key={f} value={f}>{f}</option>
                ))}
              </select>
            </div>
            <p style={{color: 'var(--text-muted)', fontSize: '0.8rem', marginTop: '0.5rem'}}>Solo se procesarán los flujos asociados estrictamente a esta fecha.</p>
          </div>

          <button 
            type="submit" 
            className="btn btn-primary" 
            style={{width: '100%', padding: '0.875rem', fontSize: '1rem'}}
            disabled={!proyecto || !fecha || isLoading}
          >
            {isLoading ? 'Reconstruyendo Flujo y Corriendo Motor...' : 'Ejecutar Validación Completa'} <ArrowRight size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
