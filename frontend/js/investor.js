import { getBase } from './data_service.js';

let chartInstance = null;

export async function render(container) {
  const base = getBase();
  
  container.innerHTML = `
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
      <h2>Reporte Inversionista</h2>
      <div>
        <button id="analyze-btn" ${!base ? 'disabled' : ''}>
          ${base ? 'Analizar Base Cargada' : 'Aún no se ha cargado ninguna base'}
        </button>
      </div>
    </div>
    
    <div id="error-container" style="color: red; margin-bottom: 1rem;"></div>

    <div class="kpi-grid" style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1.5rem; margin-bottom: 2rem;">
      <div class="card kpi-card">
        <h3>Ventas Totales</h3>
        <p id="kpi-ventas" style="font-size: 1.8rem; font-weight: 600; color: var(--accent);">-</p>
      </div>
      <div class="card kpi-card">
        <h3>Utilidad (FCO)</h3>
        <p id="kpi-utilidad" style="font-size: 1.8rem; font-weight: 600; color: var(--accent);">-</p>
      </div>
      <div class="card kpi-card">
        <h3>TIR Operativa</h3>
        <p id="kpi-tir-op" style="font-size: 1.8rem; font-weight: 600; color: var(--accent);">-</p>
      </div>
    </div>

    <div class="card" style="position: relative; height: 500px;">
      <div style="position: absolute; top: 1rem; right: 1.5rem; text-align: right;">
        <h4 style="color: var(--text-secondary); margin-bottom: 0.2rem;">TIR Inversionista</h4>
        <div id="kpi-tir-inv" style="font-size: 1.5rem; font-weight: 600; color: var(--accent);">-</div>
      </div>
      <canvas id="investorChart"></canvas>
    </div>
  `;

  const analyzeBtn = container.querySelector('#analyze-btn');
  const errorContainer = container.querySelector('#error-container');
  
  if (base) {
    analyzeBtn.addEventListener('click', async () => {
      errorContainer.textContent = 'Analizando...';
      analyzeBtn.disabled = true;
      try {
        await processData(base, container);
        errorContainer.textContent = '';
      } catch (err) {
        console.error(err);
        errorContainer.textContent = 'Error: ' + err.message;
      } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.textContent = 'Analizar Base Cargada';
      }
    });
  }
}

async function processData(base, container) {
  // 1. Fetch file if needed (if it's a URL from the backend)
  let arrayBuffer;
  if (base.url) {
    const res = await fetch(`http://localhost:5000${base.url}`);
    if (!res.ok) throw new Error('No se pudo descargar el archivo de la base de datos.');
    arrayBuffer = await res.arrayBuffer();
  } else if (base.content) {
    // Fallback if data is base64 string
    const response = await fetch(base.content);
    arrayBuffer = await response.arrayBuffer();
  } else {
    throw new Error('Formato de base inválido.');
  }

  // 2. Parse Excel/CSV with SheetJS
  const workbook = XLSX.read(arrayBuffer, { type: 'array' });
  const firstSheetName = workbook.SheetNames[0];
  const worksheet = workbook.Sheets[firstSheetName];
  // Parse to array of arrays
  const rows = XLSX.utils.sheet_to_json(worksheet, { header: 1 });

  // 3. Extracción de Datos
  const reqLines = [
    "1.0 Ingresos",
    "10.0 FCO",
    "13.2 Aportes IC",
    "13.4 Reintegros IC"
  ];
  
  const extracted = {};
  let dataStartIndex = -1;
  let labelColIndex = -1;

  // Find label column and rows
  for (let r = 0; r < rows.length; r++) {
    const row = rows[r];
    if (!row) continue;
    
    for (let c = 0; c < row.length; c++) {
      const cellValue = row[c] ? String(row[c]).trim() : "";
      if (reqLines.includes(cellValue)) {
        if (labelColIndex === -1) {
          labelColIndex = c;
          // Determine where data starts (first number after label)
          for (let i = c + 1; i < row.length; i++) {
            if (typeof row[i] === 'number') {
              dataStartIndex = i;
              break;
            }
          }
        }
        
        if (dataStartIndex !== -1) {
          // Extract data row
          const dataRow = [];
          // Assume data goes until the end of the row
          for (let i = dataStartIndex; i < row.length; i++) {
            dataRow.push(parseFloat(row[i]) || 0);
          }
          extracted[cellValue] = dataRow;
        }
      }
    }
  }

  // Verification
  const missing = reqLines.filter(line => !extracted[line]);
  if (missing.length > 0) {
    throw new Error(`Faltan las siguientes líneas exactas en la BASE: ${missing.join(', ')}`);
  }

  // Normalize array lengths (pad with 0)
  const maxLength = Math.max(...reqLines.map(line => extracted[line].length));
  reqLines.forEach(line => {
    while (extracted[line].length < maxLength) {
      extracted[line].push(0);
    }
  });

  // 4. Transformación de Signos
  const ventas = extracted["1.0 Ingresos"];
  const fco = extracted["10.0 FCO"];
  const aportes = extracted["13.2 Aportes IC"].map(v => -Math.abs(v));
  const reintegros = extracted["13.4 Reintegros IC"].map(v => Math.abs(v));

  // 5. Cálculos Financieros
  const sumVentas = ventas.reduce((a, b) => a + b, 0);
  const sumFco = fco.reduce((a, b) => a + b, 0);
  const tirOp = calculateIRR(fco);

  const flujoInv = [];
  const flujoAcumulado = [];
  let acum = 0;
  
  for (let i = 0; i < maxLength; i++) {
    const flujoPeriodo = aportes[i] + reintegros[i];
    flujoInv.push(flujoPeriodo);
    acum += flujoPeriodo;
    flujoAcumulado.push(acum);
  }

  const tirInv = calculateIRR(flujoInv);

  // Generar etiquetas (Periodo 1, Periodo 2, ...)
  const labels = Array.from({length: maxLength}, (_, i) => `Mes ${i+1}`);

  // 6. Actualizar UI
  const formatCurrency = (val) => new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(val);
  const formatPercent = (val) => (val !== null && !isNaN(val)) ? (val * 100).toFixed(2) + '%' : 'N/A';

  container.querySelector('#kpi-ventas').textContent = formatCurrency(sumVentas);
  container.querySelector('#kpi-utilidad').textContent = formatCurrency(sumFco);
  container.querySelector('#kpi-tir-op').textContent = formatPercent(tirOp);
  container.querySelector('#kpi-tir-inv').textContent = formatPercent(tirInv);

  // 7. Renderizar Gráfico
  renderChart(container.querySelector('#investorChart'), labels, aportes, reintegros, flujoAcumulado);
}

function renderChart(canvas, labels, aportes, reintegros, flujoAcumulado) {
  if (chartInstance) {
    chartInstance.destroy();
  }

  const ctx = canvas.getContext('2d');
  chartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [
        {
          type: 'line',
          label: 'Flujo Acumulado',
          data: flujoAcumulado,
          borderColor: '#681E1E',
          backgroundColor: 'rgba(104, 30, 30, 0.1)',
          borderWidth: 3,
          fill: true,
          tension: 0.3,
          yAxisID: 'y'
        },
        {
          type: 'bar',
          label: 'Aportes (Negativos)',
          data: aportes,
          backgroundColor: '#A04040',
          yAxisID: 'y'
        },
        {
          type: 'bar',
          label: 'Reintegros (Positivos)',
          data: reintegros,
          backgroundColor: '#40A060',
          yAxisID: 'y'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: {
          stacked: true
        },
        y: {
          stacked: true,
          grid: {
            color: 'rgba(0, 0, 0, 0.1)'
          }
        }
      },
      plugins: {
        tooltip: {
          callbacks: {
            label: function(context) {
              let label = context.dataset.label || '';
              if (label) {
                label += ': ';
              }
              if (context.parsed.y !== null) {
                label += new Intl.NumberFormat('es-CO', { style: 'currency', currency: 'COP', maximumFractionDigits: 0 }).format(context.parsed.y);
              }
              return label;
            }
          }
        }
      }
    }
  });
}

function calculateIRR(values, guess = 0.1) {
  // Check if there are both positive and negative values
  const hasPositive = values.some(v => v > 0);
  const hasNegative = values.some(v => v < 0);
  if (!hasPositive || !hasNegative) return null;

  const maxTries = 1000;
  let rate = guess;
  
  for (let i = 0; i < maxTries; i++) {
    let npv = 0;
    let dNpv = 0;
    for (let t = 0; t < values.length; t++) {
      npv += values[t] / Math.pow(1 + rate, t);
      dNpv -= t * values[t] / Math.pow(1 + rate, t + 1);
    }
    
    if (Math.abs(dNpv) < 1e-10) break; // Avoid division by zero
    
    const newRate = rate - npv / dNpv;
    if (Math.abs(newRate - rate) < 1e-7) {
      return newRate;
    }
    rate = newRate;
  }
  return rate;
}
