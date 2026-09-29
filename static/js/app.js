// KYC CLIENTES - Frontend Controller (with Owner Permissions & Delete Features)

document.addEventListener('DOMContentLoaded', () => {
  // Elements - Tabs
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  // Elements - Upload
  const dropZone = document.getElementById('drop-zone');
  const fileInput = document.getElementById('file-input');
  const dropIdle = document.getElementById('drop-idle');
  const dropProcessing = document.getElementById('drop-processing');
  const processingText = document.getElementById('processing-text');
  const dropPreview = document.getElementById('drop-preview');
  const imgPreview = document.getElementById('img-preview');
  const pdfPreviewBox = document.getElementById('pdf-preview-box');
  const pdfPreviewName = document.getElementById('pdf-preview-name');
  const btnChangeFile = document.getElementById('btn-change-file');
  const btnProcessUpload = document.getElementById('btn-process-upload');
  const checkAutoSave = document.getElementById('check-auto-save');
  const inputTipoDoc = document.getElementById('input-tipo-doc');
  const inputNotas = document.getElementById('input-notas');

  // Elements - Results
  const repeatBanner = document.getElementById('repeat-banner');
  const resCedula = document.getElementById('res-cedula');
  const resNombre = document.getElementById('res-nombre');
  const resTipo = document.getElementById('res-tipo');
  const resFechaHora = document.getElementById('res-fecha-hora');
  const resProvider = document.getElementById('res-provider');
  const resCloudLink = document.getElementById('res-cloud-link');
  const resRawOcr = document.getElementById('res-raw-ocr');
  const boxConfirmUpdate = document.getElementById('box-confirm-update');
  const btnManualConfirm = document.getElementById('btn-manual-confirm');

  // Elements - Search Client & Frequency
  const formCheckClient = document.getElementById('form-check-client');
  const searchCedula = document.getElementById('search-cedula');
  const searchNombre = document.getElementById('search-nombre');
  const searchResultsPanel = document.getElementById('search-results-panel');
  const frequencyHeroCard = document.getElementById('frequency-hero-card');
  const frequencyIconBox = document.getElementById('frequency-icon-box');
  const frequencyTag = document.getElementById('frequency-tag');
  const frequencyTitle = document.getElementById('frequency-title');
  const frequencySubtitle = document.getElementById('frequency-subtitle');
  const frequencyNumber = document.getElementById('frequency-number');
  const clientHistoryRows = document.getElementById('client-history-rows');

  // Elements - General Table & Stats
  const statTotalRecords = document.getElementById('stat-total-records');
  const statUniqueClients = document.getElementById('stat-unique-clients');
  const statDuplicates = document.getElementById('stat-duplicates');
  const allRecordsTbody = document.getElementById('all-records-tbody');
  const tableFilterInput = document.getElementById('table-filter-input');
  const btnRefreshTable = document.getElementById('btn-refresh-table');

  // Elements - Share Link Modal
  const btnShareLink = document.getElementById('btn-share-link');
  const modalShare = document.getElementById('modal-share');
  const btnCloseShare = document.getElementById('btn-close-share');
  const btnDismissShare = document.getElementById('btn-dismiss-share');

  // Elements - Users Tab & Modal
  const usersTbody = document.getElementById('users-tbody');
  const btnOpenCreateUser = document.getElementById('btn-open-create-user');
  const modalCreateUser = document.getElementById('modal-create-user');
  const btnCloseCreateUser = document.getElementById('btn-close-create-user');
  const btnCancelCreateUser = document.getElementById('btn-cancel-create-user');
  const formCreateUser = document.getElementById('form-create-user');
  const createUserStatus = document.getElementById('create-user-status');

  // Elements - Cloud Modal
  const btnCloudConfig = document.getElementById('btn-cloud-config');
  const modalCloud = document.getElementById('modal-cloud');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const btnCancelModal = document.getElementById('btn-cancel-modal');
  const btnSaveCloud = document.getElementById('btn-save-cloud');
  const configProvider = document.getElementById('config-provider');
  const boxCloudinary = document.getElementById('box-cloudinary-fields');
  const boxS3 = document.getElementById('box-s3-fields');
  const cloudTestStatus = document.getElementById('cloud-test-status');
  const navCloudBadge = document.getElementById('nav-cloud-badge');

  // Elements - Viewer Modal
  const modalViewer = document.getElementById('modal-viewer');
  const btnCloseViewer = document.getElementById('btn-close-viewer');
  const viewerTitle = document.getElementById('viewer-title');
  const viewerImg = document.getElementById('viewer-img');
  const viewerFrame = document.getElementById('viewer-frame');

  let currentFile = null;
  let lastUploadedData = null;
  let isCurrentUserOwner = false;

  // 1. Tab Switching
  tabButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');
      tabButtons.forEach(b => {
        b.classList.remove('active', 'border-indigo-500', 'text-indigo-400');
        b.classList.add('border-transparent', 'text-slate-400');
      });
      btn.classList.add('active', 'border-indigo-500', 'text-indigo-400');
      btn.classList.remove('border-transparent', 'text-slate-400');

      tabContents.forEach(content => {
        if (content.id === targetTab) {
          content.classList.remove('hidden');
          content.classList.add('block');
        } else {
          content.classList.remove('block');
          content.classList.add('hidden');
        }
      });

      if (targetTab === 'tab-records') {
        loadRecords();
      } else if (targetTab === 'tab-users') {
        loadUsers();
      }
    });
  });

  // 2. Drag & Drop Handling
  if (dropZone) {
    dropZone.addEventListener('click', (e) => {
      if (e.target !== btnChangeFile) {
        fileInput.click();
      }
    });

    ['dragenter', 'dragover'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.add('drop-hover');
      });
    });

    ['dragleave', 'drop'].forEach(eventName => {
      dropZone.addEventListener(eventName, (e) => {
        e.preventDefault();
        dropZone.classList.remove('drop-hover');
      });
    });

    dropZone.addEventListener('drop', (e) => {
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        handleFileSelected(e.dataTransfer.files[0]);
      }
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', () => {
      if (fileInput.files && fileInput.files.length > 0) {
        handleFileSelected(fileInput.files[0]);
      }
    });
  }

  if (btnChangeFile) {
    btnChangeFile.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.value = '';
      currentFile = null;
      dropPreview.classList.add('hidden');
      dropIdle.classList.remove('hidden');
    });
  }

  function handleFileSelected(file) {
    currentFile = file;
    dropIdle.classList.add('hidden');
    dropPreview.classList.remove('hidden');

    const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');
    if (isPdf) {
      imgPreview.classList.add('hidden');
      pdfPreviewBox.classList.remove('hidden');
      pdfPreviewName.textContent = file.name;
    } else {
      pdfPreviewBox.classList.add('hidden');
      imgPreview.classList.remove('hidden');
      const reader = new FileReader();
      reader.onload = (e) => {
        imgPreview.src = e.target.result;
      };
      reader.readAsDataURL(file);
    }
  }

  // 3. Process & Upload with OCR
  if (btnProcessUpload) {
    btnProcessUpload.addEventListener('click', () => {
      if (!currentFile) {
        alert('Por favor seleccione o arrastre una imagen de cédula o pasaporte primero.');
        return;
      }
      processUpload();
    });
  }

  async function processUpload() {
    dropPreview.classList.add('hidden');
    dropProcessing.classList.remove('hidden');
    btnProcessUpload.disabled = true;

    // Client-side OCR fallback for Linux cloud hosting
    let clientOcrText = '';
    const isImage = currentFile && (currentFile.type.startsWith('image/') || !currentFile.name.toLowerCase().endsWith('.pdf'));
    if (window.Tesseract && isImage) {
      try {
        processingText.textContent = "Extrayendo datos de la cédula con OCR...";
        const ocrRes = await Tesseract.recognize(currentFile, 'spa');
        if (ocrRes && ocrRes.data && ocrRes.data.text) {
          clientOcrText = ocrRes.data.text;
        }
      } catch (ocrErr) {
        console.warn('Client OCR warning:', ocrErr);
      }
    }

    const formData = new FormData();
    formData.append('file', currentFile);
    formData.append('auto_save', checkAutoSave.checked ? 'true' : 'false');
    formData.append('tipo_documento', inputTipoDoc.value);
    formData.append('notas', inputNotas.value);
    if (clientOcrText) {
      formData.append('client_ocr_text', clientOcrText);
    }

    try {
      processingText.textContent = "Subiendo archivo y registrando en la nube...";
      const res = await fetch('/api/scan-and-upload', {
        method: 'POST',
        body: formData
      });
      const data = await res.json();

      if (!data.success) {
        alert('Error: ' + (data.error || 'No se pudo procesar el documento'));
        return;
      }

      lastUploadedData = data;
      renderExtractedData(data);
      loadStats();

    } catch (err) {
      console.error(err);
      alert('Error de conexión al procesar el documento.');
    } finally {
      dropProcessing.classList.add('hidden');
      dropPreview.classList.remove('hidden');
      btnProcessUpload.disabled = false;
    }
  }

  function renderExtractedData(data) {
    resCedula.value = data.documento_numero || '';
    resNombre.value = data.nombre_apellido || '';
    resTipo.value = data.tipo_documento || 'Cédula de Identidad';
    resFechaHora.value = data.fecha_hora || '';
    resProvider.value = (data.cloud_provider || 'local').toUpperCase();
    resRawOcr.textContent = data.ocr_raw_text || '(Sin texto detectado)';

    if (data.file_url) {
      resCloudLink.href = data.file_url;
      resCloudLink.classList.remove('hidden');
    } else {
      resCloudLink.classList.add('hidden');
    }

    // Display times registered banner
    repeatBanner.classList.remove('hidden');
    const times = data.times_registered || 1;
    
    if (times > 1) {
      repeatBanner.className = 'mb-5 p-4 rounded-xl border border-amber-500/40 bg-amber-500/10 text-amber-200';
      repeatBanner.innerHTML = `
        <div class="flex items-start space-x-3">
          <i class="fa-solid fa-triangle-exclamation text-amber-400 text-xl mt-0.5"></i>
          <div>
            <h4 class="font-bold text-amber-300">¡Alerta de Registro Recurrente!</h4>
            <p class="text-xs mt-1">Este documento (Cédula: <b>${data.documento_numero}</b>) ya ha sido registrado un total de <b class="text-base text-amber-200">${times} VECES</b> en el sistema.</p>
            <button type="button" onclick="quickCheckClient('${data.documento_numero}', '${data.nombre_apellido}')" class="mt-2 text-xs font-semibold underline text-amber-300 hover:text-amber-100 flex items-center space-x-1">
              <span>Ver historial de registros de esta cédula</span>
              <i class="fa-solid fa-arrow-right"></i>
            </button>
          </div>
        </div>
      `;
    } else {
      repeatBanner.className = 'mb-5 p-4 rounded-xl border border-emerald-500/40 bg-emerald-500/10 text-emerald-200';
      repeatBanner.innerHTML = `
        <div class="flex items-start space-x-3">
          <i class="fa-solid fa-circle-check text-emerald-400 text-xl mt-0.5"></i>
          <div>
            <h4 class="font-bold text-emerald-300">¡Nuevo Registro Exitoso!</h4>
            <p class="text-xs mt-1">Primer registro en el sistema para esta cédula. Fecha y hora registrada: <span class="font-mono">${data.fecha_hora}</span>.</p>
          </div>
        </div>
      `;
    }

    if (!checkAutoSave.checked) {
      boxConfirmUpdate.classList.remove('hidden');
    } else {
      boxConfirmUpdate.classList.add('hidden');
    }
  }

  // 4. Manual Confirm / Edit
  if (btnManualConfirm) {
    btnManualConfirm.addEventListener('click', async () => {
      if (!lastUploadedData) return;

      const payload = {
        documento_numero: resCedula.value.trim(),
        nombre_apellido: resNombre.value.trim(),
        tipo_documento: resTipo.value.trim(),
        file_url: lastUploadedData.file_url,
        file_name: lastUploadedData.file_name,
        cloud_provider: lastUploadedData.cloud_provider,
        public_id: lastUploadedData.public_id,
        ocr_raw_text: lastUploadedData.ocr_raw_text,
        notas: inputNotas.value.trim()
      };

      try {
        const res = await fetch('/api/confirm-save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          alert(`¡Registro guardado exitosamente! Ha sido registrado ${data.times_registered} veces.`);
          boxConfirmUpdate.classList.add('hidden');
          loadStats();
        } else {
          alert('Error: ' + data.error);
        }
      } catch (e) {
        alert('Error al confirmar guardado.');
      }
    });
  }

  // 5. Query Client & Registration Frequency (Requisito clave)
  if (formCheckClient) {
    formCheckClient.addEventListener('submit', async (e) => {
      e.preventDefault();
      const doc = searchCedula.value.trim();
      const nom = searchNombre.value.trim();

      if (!doc && !nom) {
        alert('Por favor ingrese al menos el número de cédula o el nombre.');
        return;
      }

      try {
        const res = await fetch(`/api/check-client?cedula=${encodeURIComponent(doc)}&nombre=${encodeURIComponent(nom)}`);
        const data = await res.json();

        if (!data.success) {
          alert(data.error || 'Error al consultar cliente');
          return;
        }

        renderClientFrequencyResults(data);
      } catch (err) {
        console.error(err);
        alert('Error al conectar con el servidor.');
      }
    });
  }

  window.quickCheckClient = (cedula, nombre) => {
    const searchTabBtn = document.querySelector('[data-tab="tab-search"]');
    if (searchTabBtn) searchTabBtn.click();
    searchCedula.value = cedula || '';
    searchNombre.value = nombre || '';
    formCheckClient.dispatchEvent(new Event('submit'));
  };

  function renderClientFrequencyResults(data) {
    searchResultsPanel.classList.remove('hidden');
    frequencyNumber.textContent = data.times_registered;

    if (data.times_registered === 0) {
      frequencyHeroCard.className = 'rounded-2xl p-6 border border-slate-700 bg-slate-800/40 flex flex-col sm:flex-row items-center justify-between gap-6';
      frequencyIconBox.className = 'w-16 h-16 rounded-2xl flex items-center justify-center text-3xl font-black bg-slate-700/50 text-slate-400';
      frequencyIconBox.innerHTML = '<i class="fa-solid fa-user-xmark"></i>';
      frequencyTag.className = 'text-xs uppercase px-2.5 py-1 rounded-full font-bold tracking-wider bg-slate-700 text-slate-300';
      frequencyTag.textContent = 'NO REGISTRADO';
      frequencyTitle.textContent = 'Sin Registros Previos';
      frequencySubtitle.textContent = `No se encontraron registros para la cédula "${data.search_cedula}" o nombre "${data.search_nombre}".`;
      clientHistoryRows.innerHTML = `<tr><td colspan="7" class="text-center py-6 text-slate-500">No hay documentos cargados para este criterio.</td></tr>`;
      return;
    }

    if (data.times_registered === 1) {
      frequencyHeroCard.className = 'rounded-2xl p-6 border border-emerald-500/40 bg-emerald-950/20 flex flex-col sm:flex-row items-center justify-between gap-6';
      frequencyIconBox.className = 'w-16 h-16 rounded-2xl flex items-center justify-center text-3xl font-black bg-emerald-500/20 text-emerald-400';
      frequencyIconBox.innerHTML = '<i class="fa-solid fa-user-check"></i>';
      frequencyTag.className = 'text-xs uppercase px-2.5 py-1 rounded-full font-bold tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
      frequencyTag.textContent = 'CLIENTE ÚNICO';
      frequencyTitle.textContent = `${data.history[0].nombre_apellido}`;
      frequencySubtitle.textContent = `Cédula: ${data.history[0].documento_numero} • Registrado 1 sola vez el ${data.first_registered}`;
    } else {
      frequencyHeroCard.className = 'rounded-2xl p-6 border border-amber-500/50 bg-amber-950/20 flex flex-col sm:flex-row items-center justify-between gap-6';
      frequencyIconBox.className = 'w-16 h-16 rounded-2xl flex items-center justify-center text-3xl font-black bg-amber-500/20 text-amber-400';
      frequencyIconBox.innerHTML = '<i class="fa-solid fa-repeat"></i>';
      frequencyTag.className = 'text-xs uppercase px-2.5 py-1 rounded-full font-bold tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/30';
      frequencyTag.textContent = 'REGISTRO RECURRENTE / DUPLICADO';
      frequencyTitle.textContent = `${data.history[0].nombre_apellido}`;
      frequencySubtitle.textContent = `Cédula: ${data.history[0].documento_numero} • Registrado ${data.times_registered} veces (Primer registro: ${data.first_registered}, Último: ${data.last_registered})`;
    }

    clientHistoryRows.innerHTML = data.history.map((rec, index) => `
      <tr class="hover:bg-slate-800/40 transition">
        <td class="py-3 font-mono text-xs text-slate-400">#${data.history.length - index}</td>
        <td class="py-3 font-mono text-xs text-slate-200">
          <i class="fa-regular fa-clock text-indigo-400 mr-1"></i> ${rec.fecha_hora}
        </td>
        <td class="py-3 text-xs text-slate-300">${rec.tipo_documento || 'Cédula'}</td>
        <td class="py-3 text-xs font-semibold text-white">${rec.nombre_apellido}</td>
        <td class="py-3 text-xs text-slate-400">
          <span class="font-mono text-[11px]"><i class="fa-solid fa-user-circle mr-1"></i>${rec.uploaded_by || 'admin'}</span>
        </td>
        <td class="py-3 text-xs">
          <span class="px-2 py-0.5 rounded-full text-[11px] font-bold ${rec.file_cloud_provider === 'cloudinary' ? 'bg-sky-500/20 text-sky-300' : (rec.file_cloud_provider === 's3' ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-700 text-slate-300')}">
            ${(rec.file_cloud_provider || 'local').toUpperCase()}
          </span>
        </td>
        <td class="py-3 text-right">
          <button onclick="viewDoc('${rec.file_url}', '${rec.documento_numero} - ${rec.nombre_apellido}')" class="text-xs bg-indigo-600/30 hover:bg-indigo-600/60 text-indigo-300 px-2.5 py-1 rounded-lg transition font-medium">
            <i class="fa-solid fa-eye mr-1"></i> Ver
          </button>
        </td>
      </tr>
    `).join('');
  }

  // 6. General Records Table (with Owner Delete action)
  async function loadRecords() {
    const q = tableFilterInput.value.trim();
    try {
      const res = await fetch(`/api/records?q=${encodeURIComponent(q)}`);
      const data = await res.json();
      
      if (!data.success || !data.records.length) {
        allRecordsTbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-slate-500">No se encontraron registros.</td></tr>`;
        return;
      }

      isCurrentUserOwner = Boolean(data.is_owner);

      allRecordsTbody.innerHTML = data.records.map(rec => `
        <tr class="hover:bg-slate-800/40 transition">
          <td class="py-3 font-mono text-xs text-slate-400">${rec.id}</td>
          <td class="py-3 font-bold text-indigo-300 text-xs">${rec.documento_numero}</td>
          <td class="py-3 text-xs font-semibold text-white">${rec.nombre_apellido}</td>
          <td class="py-3 text-xs text-slate-300">${rec.tipo_documento}</td>
          <td class="py-3 font-mono text-xs text-slate-200">
            <i class="fa-regular fa-clock text-slate-400 mr-1"></i> ${rec.fecha_hora}
          </td>
          <td class="py-3 text-xs font-mono text-slate-300">
            <span class="bg-slate-900 px-2 py-0.5 rounded border border-slate-800 text-[11px]">${rec.uploaded_by || 'admin'}</span>
          </td>
          <td class="py-3 text-xs">
            <span class="px-2 py-0.5 rounded-full text-[11px] font-bold ${rec.file_cloud_provider === 'cloudinary' ? 'bg-sky-500/20 text-sky-300' : (rec.file_cloud_provider === 's3' ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-700 text-slate-300')}">
              ${(rec.file_cloud_provider || 'local').toUpperCase()}
            </span>
          </td>
          <td class="py-3 text-right space-x-1.5">
            <button onclick="viewDoc('${rec.file_url}', '${rec.documento_numero} - ${rec.nombre_apellido}')" class="text-xs bg-indigo-600/30 hover:bg-indigo-600/60 text-indigo-300 px-2.5 py-1 rounded-lg transition font-medium" title="Ver documento">
              <i class="fa-solid fa-eye"></i>
            </button>
            ${isCurrentUserOwner ? `
            <button onclick="deleteDoc(${rec.id}, '${rec.documento_numero}')" class="text-xs bg-rose-600/30 hover:bg-rose-600/60 text-rose-300 px-2.5 py-1 rounded-lg transition font-medium" title="Eliminar registro (Solo Propietario)">
              <i class="fa-solid fa-trash"></i>
            </button>
            ` : ''}
          </td>
        </tr>
      `).join('');

    } catch (e) {
      console.error(e);
      allRecordsTbody.innerHTML = `<tr><td colspan="8" class="text-center py-8 text-rose-400">Error cargando registros.</td></tr>`;
    }
  }

  // Delete Record function (Owner only)
  window.deleteDoc = async (id, docNum) => {
    if (!confirm(`¿Está seguro de eliminar permanentemente el registro #${id} (Cédula: ${docNum}) y sus archivos asociados?`)) {
      return;
    }

    try {
      const res = await fetch(`/api/records/${id}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (data.success) {
        alert(data.message);
        loadRecords();
        loadStats();
      } else {
        alert('Error: ' + data.error);
      }
    } catch (e) {
      alert('Error de conexión al eliminar registro.');
    }
  };

  if (tableFilterInput) {
    tableFilterInput.addEventListener('input', () => {
      loadRecords();
    });
  }

  if (btnRefreshTable) {
    btnRefreshTable.addEventListener('click', () => {
      loadRecords();
      loadStats();
    });
  }

  // 7. Load Stats
  async function loadStats() {
    try {
      const res = await fetch('/api/stats');
      const data = await res.json();
      if (data.success) {
        statTotalRecords.textContent = data.stats.total_records || 0;
        statUniqueClients.textContent = data.stats.unique_clients || 0;
        statDuplicates.textContent = data.stats.frequent_clients ? data.stats.frequent_clients.length : 0;
        
        isCurrentUserOwner = Boolean(data.is_owner);
        const prov = (data.cloud.provider || 'local').toUpperCase();
        if (navCloudBadge) navCloudBadge.textContent = `Nube: ${prov}`;
      }
    } catch (e) {
      console.error(e);
    }
  }

  // 8. Viewer Modal
  window.viewDoc = (url, title) => {
    viewerTitle.textContent = title;
    const isPdf = url.toLowerCase().includes('.pdf');
    if (isPdf) {
      viewerImg.classList.add('hidden');
      viewerFrame.classList.remove('hidden');
      viewerFrame.src = url;
    } else {
      viewerFrame.classList.add('hidden');
      viewerImg.classList.remove('hidden');
      viewerImg.src = url;
    }
    modalViewer.classList.remove('hidden');
  };

  btnCloseViewer.addEventListener('click', () => {
    modalViewer.classList.add('hidden');
    viewerImg.src = '';
    viewerFrame.src = '';
  });

  // 9. Share Link Modal Controls
  if (btnShareLink) {
    btnShareLink.addEventListener('click', () => {
      modalShare.classList.remove('hidden');
    });
  }

  if (btnCloseShare) btnCloseShare.addEventListener('click', () => modalShare.classList.add('hidden'));
  if (btnDismissShare) btnDismissShare.addEventListener('click', () => modalShare.classList.add('hidden'));

  window.copyNetworkUrl = () => {
    const input = document.getElementById('modal-network-url');
    input.select();
    navigator.clipboard.writeText(input.value).then(() => {
      const btnText = document.getElementById('copy-network-btn-text');
      btnText.textContent = '¡Copiado!';
      setTimeout(() => { btnText.textContent = 'Copiar'; }, 2000);
    });
  };

  window.copyLocalUrl = () => {
    const input = document.getElementById('modal-local-url');
    input.select();
    navigator.clipboard.writeText(input.value).then(() => {
      alert('¡Enlace local copiado!');
    });
  };

  // 10. Users Management (with Owner Delete action)
  async function loadUsers() {
    if (!usersTbody) return;
    try {
      const res = await fetch('/api/users');
      const data = await res.json();
      if (data.success && data.users) {
        const isOwner = Boolean(data.is_owner);
        usersTbody.innerHTML = data.users.map(u => `
          <tr class="hover:bg-slate-800/40 transition">
            <td class="py-3 font-mono text-xs text-slate-400">#${u.id}</td>
            <td class="py-3 font-bold text-white text-xs font-mono">
              <i class="fa-solid fa-user-circle ${u.role === 'Propietario' ? 'text-amber-400' : 'text-indigo-400'} mr-1.5"></i>${u.username}
            </td>
            <td class="py-3 text-xs text-slate-200">${u.full_name}</td>
            <td class="py-3 text-xs">
              <span class="px-2.5 py-0.5 rounded-full text-[11px] font-bold ${u.role === 'Propietario' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/30' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'}">
                ${u.role}
              </span>
            </td>
            <td class="py-3 font-mono text-xs text-slate-400">
              ${u.last_login || 'Nunca'}
            </td>
            <td class="py-3 text-xs">
              <span class="text-emerald-400 font-semibold text-[11px] flex items-center space-x-1">
                <span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>
                <span>Activo</span>
              </span>
            </td>
            ${isOwner ? `
            <td class="py-3 text-right">
              ${u.role === 'Propietario' ? `
                <span class="text-[11px] text-amber-400 font-semibold italic"><i class="fa-solid fa-crown mr-1"></i>Propietario</span>
              ` : `
                <button onclick="deleteUserAccount(${u.id}, '${u.username}')" class="text-xs bg-rose-600/30 hover:bg-rose-600/60 text-rose-300 px-2.5 py-1 rounded-lg transition font-medium" title="Eliminar usuario">
                  <i class="fa-solid fa-trash mr-1"></i> Eliminar
                </button>
              `}
            </td>
            ` : ''}
          </tr>
        `).join('');
      }
    } catch (e) {
      console.error(e);
      usersTbody.innerHTML = `<tr><td colspan="7" class="text-center py-6 text-rose-400">Error cargando usuarios.</td></tr>`;
    }
  }

  // Delete User function (Owner only)
  window.deleteUserAccount = async (userId, username) => {
    if (!confirm(`¿Está seguro de eliminar al usuario '${username}'? Esta persona ya no podrá acceder al sistema.`)) {
      return;
    }

    try {
      const res = await fetch(`/api/users/${userId}`, {
        method: 'DELETE'
      });
      const data = await res.json();
      if (data.success) {
        alert(data.message);
        loadUsers();
      } else {
        alert('Error: ' + data.error);
      }
    } catch (e) {
      alert('Error al intentar eliminar el usuario.');
    }
  };

  if (btnOpenCreateUser) {
    btnOpenCreateUser.addEventListener('click', () => {
      createUserStatus.classList.add('hidden');
      formCreateUser.reset();
      modalCreateUser.classList.remove('hidden');
    });
  }

  if (btnCloseCreateUser) btnCloseCreateUser.addEventListener('click', () => modalCreateUser.classList.add('hidden'));
  if (btnCancelCreateUser) btnCancelCreateUser.addEventListener('click', () => modalCreateUser.classList.add('hidden'));

  if (formCreateUser) {
    formCreateUser.addEventListener('submit', async (e) => {
      e.preventDefault();
      const payload = {
        full_name: document.getElementById('new-fullname').value.trim(),
        username: document.getElementById('new-username').value.trim(),
        role: document.getElementById('new-role').value,
        password: document.getElementById('new-password').value.trim()
      };

      try {
        const res = await fetch('/api/users', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.success) {
          createUserStatus.className = 'text-xs p-2 rounded font-medium bg-emerald-500/20 text-emerald-300';
          createUserStatus.textContent = '✅ ' + data.message;
          createUserStatus.classList.remove('hidden');
          setTimeout(() => {
            modalCreateUser.classList.add('hidden');
            loadUsers();
          }, 1200);
        } else {
          createUserStatus.className = 'text-xs p-2 rounded font-medium bg-rose-500/20 text-rose-300';
          createUserStatus.textContent = '❌ ' + data.error;
          createUserStatus.classList.remove('hidden');
        }
      } catch (err) {
        createUserStatus.className = 'text-xs p-2 rounded font-medium bg-rose-500/20 text-rose-300';
        createUserStatus.textContent = '❌ Error de comunicación con el servidor.';
        createUserStatus.classList.remove('hidden');
      }
    });
  }

  // 11. Cloud Config Modal
  if (btnCloudConfig) {
    btnCloudConfig.addEventListener('click', () => {
      modalCloud.classList.remove('hidden');
    });
  }

  btnCloseModal.addEventListener('click', () => modalCloud.classList.add('hidden'));
  btnCancelModal.addEventListener('click', () => modalCloud.classList.add('hidden'));

  configProvider.addEventListener('change', () => {
    const val = configProvider.value;
    if (val === 'cloudinary') {
      boxCloudinary.classList.remove('hidden');
      boxS3.classList.add('hidden');
    } else if (val === 's3') {
      boxCloudinary.classList.add('hidden');
      boxS3.classList.remove('hidden');
    } else {
      boxCloudinary.classList.add('hidden');
      boxS3.classList.add('hidden');
    }
  });

  btnSaveCloud.addEventListener('click', async () => {
    const prov = configProvider.value;
    let payload = { provider: prov };

    if (prov === 'cloudinary') {
      payload.cloud_name = document.getElementById('cfg-c-name').value.trim();
      payload.api_key = document.getElementById('cfg-c-key').value.trim();
      payload.api_secret = document.getElementById('cfg-c-secret').value.trim();
    } else if (prov === 's3') {
      payload.bucket = document.getElementById('cfg-s3-bucket').value.trim();
      payload.access_key = document.getElementById('cfg-s3-key').value.trim();
      payload.secret_key = document.getElementById('cfg-s3-secret').value.trim();
      payload.region = document.getElementById('cfg-s3-region').value.trim();
    }

    cloudTestStatus.classList.remove('hidden');
    cloudTestStatus.className = 'text-xs p-2 rounded font-medium bg-indigo-500/20 text-indigo-300';
    cloudTestStatus.textContent = 'Probando conexión con la nube...';

    try {
      const res = await fetch('/api/config/cloud', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();

      if (data.success) {
        cloudTestStatus.className = 'text-xs p-2 rounded font-medium bg-emerald-500/20 text-emerald-300';
        cloudTestStatus.textContent = '✅ ' + data.message;
        setTimeout(() => {
          modalCloud.classList.add('hidden');
          loadStats();
        }, 1200);
      } else {
        cloudTestStatus.className = 'text-xs p-2 rounded font-medium bg-rose-500/20 text-rose-300';
        cloudTestStatus.textContent = '❌ Error: ' + data.error;
      }
    } catch (e) {
      cloudTestStatus.className = 'text-xs p-2 rounded font-medium bg-rose-500/20 text-rose-300';
      cloudTestStatus.textContent = '❌ Error al guardar configuración de nube.';
    }
  });

  // Initial load
  loadStats();
});
