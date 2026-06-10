import { useState } from 'react';
import { ShieldCheck, ShieldAlert, AlertTriangle, Info, CheckCircle2, ChevronDown, ChevronRight, XCircle } from 'lucide-react';

export default function DashboardView({ report, selections, onBack }) {
  const { resumen_ejecutivo: res, hallazgos, validaciones_ok, encabezado } = report;
  const [expanded, setExpanded] = useState({});

  const toggleExpand = (id) => {
    setExpanded(prev => ({...prev, [id]: !prev[id]}));
  };

  const statusColor = encabezado.estado === 'OK' ? 'var(--color-success)' :
                      encabezado.estado === 'REVISAR' ? 'var(--color-warning)' : 'var(--color-critical)';

  return (
    <div>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem'}}>
        <div>
          <button className="btn btn-secondary" onClick={onBack} style={{marginBottom: '1rem', padding: '0.25rem 0.5rem', fontSize: '0.75rem'}}>
            ← Cambiar Selección
          </button>
          <h1 style={{fontSize: '2rem', marginBottom: '0.25rem'}}>
            Diagnóstico Financiero
          </h1>
          <div style={{color: 'var(--text-secondary)'}}>
            Proyecto: <span style={{fontWeight: 600, color: 'var(--text-primary)'}}>{encabezado.proyecto}</span> | 
            Versión: <span style={{fontWeight: 600, color: 'var(--text-primary)'}}>{encabezado.fecha_datos.split('T')[0]}</span>
          </div>
        </div>
        
        <div style={{textAlign: 'right'}}>
          <div style={{fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-secondary)', fontWeight: 600}}>Score Integridad</div>
          <div className="mono" style={{fontSize: '3rem', fontWeight: 700, color: statusColor, lineHeight: 1}}>
            {encabezado.score}<span style={{fontSize: '1.5rem'}}>%</span>
          </div>
          <div style={{fontWeight: 600, letterSpacing: '0.05em', color: statusColor}}>{encabezado.estado}</div>
        </div>
      </div>

      {/* SUMMARY CARDS */}
      <div style={{display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '2rem'}}>
        <SummaryCard icon={<ShieldCheck color="var(--color-success)"/>} label="Aprobadas" value={res.aprobadas} total={res.total_validaciones} />
        <SummaryCard icon={<XCircle color="var(--color-critical)"/>} label="Errores Críticos" value={res.errores_criticos} />
        <SummaryCard icon={<AlertTriangle color="var(--color-warning)"/>} label="Advertencias" value={res.advertencias} />
        <SummaryCard icon={<Info color="var(--color-info)"/>} label="Informativos" value={res.informativos} />
      </div>

      {/* NARRATIVA EJECUTIVA */}
      <div className="card" style={{marginBottom: '2rem', borderColor: statusColor}}>
        <h3 style={{marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem'}}>
          {encabezado.estado === 'OK' ? <ShieldCheck color={statusColor}/> : <ShieldAlert color={statusColor} />}
          Dictamen Automático
        </h3>
        <p style={{color: 'var(--text-secondary)', fontSize: '1rem', lineHeight: 1.6}}>
          {res.narrativa}
        </p>
      </div>

      {/* HALLAZGOS (ALERTAS) */}
      <h3 style={{marginBottom: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem'}}>
        Detalle de Hallazgos ({hallazgos.length})
      </h3>
      
      {hallazgos.length === 0 ? (
        <div className="card" style={{textAlign: 'center', padding: '3rem 1rem'}}>
          <CheckCircle2 color="var(--color-success)" size={48} style={{margin: '0 auto 1rem auto'}} />
          <h3>Sin Inconsistencias</h3>
          <p style={{color: 'var(--text-secondary)'}}>Todas las reglas del motor fueron superadas exitosamente.</p>
        </div>
      ) : (
        <div style={{display: 'flex', flexDirection: 'column', gap: '1rem'}}>
          {hallazgos.map(h => (
            <div key={h.id} className="card" style={{padding: 0, overflow: 'hidden'}}>
              <div 
                style={{padding: '1.25rem', display: 'flex', gap: '1rem', cursor: 'pointer', backgroundColor: 'var(--bg-surface)'}}
                onClick={() => toggleExpand(h.id)}
              >
                <div style={{marginTop: '0.25rem'}}>
                  {h.severidad === 'critico' && <XCircle color="var(--color-critical)"/>}
                  {h.severidad === 'advertencia' && <AlertTriangle color="var(--color-warning)"/>}
                  {h.severidad === 'informativo' && <Info color="var(--color-info)"/>}
                </div>
                <div style={{flex: 1}}>
                  <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.25rem'}}>
                    <h4 style={{fontSize: '1rem'}}>{h.nombre}</h4>
                    <span className={`badge badge-${h.severidad}`}>{h.severidad.toUpperCase()}</span>
                  </div>
                  <p style={{color: 'var(--text-secondary)', fontSize: '0.875rem', marginBottom: '0.5rem'}}>{h.descripcion}</p>
                  
                  {h.lineas_afectadas && h.lineas_afectadas.length > 0 && (
                    <div style={{fontSize: '0.75rem', color: 'var(--text-muted)'}}>
                      <span style={{fontWeight: 600}}>Líneas:</span> {h.lineas_afectadas.join(', ')}
                    </div>
                  )}
                </div>
                <div style={{alignSelf: 'center', color: 'var(--text-muted)'}}>
                  {expanded[h.id] ? <ChevronDown /> : <ChevronRight />}
                </div>
              </div>

              {expanded[h.id] && (
                <div style={{padding: '1.25rem', backgroundColor: 'var(--bg-surface-elevated)', borderTop: '1px solid var(--border-subtle)'}}>
                  
                  <div style={{display: 'flex', gap: '2rem', marginBottom: '1.5rem'}}>
                    {h.valor_observado !== null && (
                      <div>
                        <div style={{fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-secondary)'}}>Valor Observado</div>
                        <div className="mono" style={{fontSize: '1.125rem'}}>{h.valor_observado}</div>
                      </div>
                    )}
                    {h.valor_esperado !== null && (
                      <div>
                        <div style={{fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-secondary)'}}>Valor Esperado</div>
                        <div className="mono" style={{fontSize: '1.125rem'}}>{h.valor_esperado}</div>
                      </div>
                    )}
                    {h.diferencia !== null && (
                      <div>
                        <div style={{fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-secondary)'}}>Diferencia</div>
                        <div className="mono" style={{fontSize: '1.125rem', color: 'var(--color-critical)'}}>{h.diferencia}</div>
                      </div>
                    )}
                  </div>

                  <div style={{padding: '1rem', backgroundColor: 'var(--bg-app)', borderRadius: 'var(--radius-sm)', borderLeft: '3px solid var(--accent-color)'}}>
                    <div style={{fontSize: '0.75rem', fontWeight: 600, color: 'var(--accent-color)', marginBottom: '0.25rem', textTransform: 'uppercase'}}>Diagnóstico Analista</div>
                    <p style={{fontSize: '0.875rem', lineHeight: 1.5, color: 'var(--text-primary)'}}>{h.explicacion_financiera}</p>
                  </div>

                </div>
              )}
            </div>
          ))}
        </div>
      )}

    </div>
  );
}

function SummaryCard({icon, label, value, total}) {
  return (
    <div className="card" style={{display: 'flex', alignItems: 'center', gap: '1rem', padding: '1.25rem'}}>
      <div>{icon}</div>
      <div>
        <div style={{fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 600}}>{label}</div>
        <div style={{fontSize: '1.5rem', fontWeight: 700}}>
          {value} {total && <span style={{fontSize: '1rem', color: 'var(--text-muted)'}}>/ {total}</span>}
        </div>
      </div>
    </div>
  );
}
