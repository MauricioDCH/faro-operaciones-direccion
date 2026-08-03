(() => {
  const dialog = document.querySelector('[data-import-dialog]');
  document.querySelectorAll('[data-open-import]').forEach((button) => {
    button.addEventListener('click', () => dialog?.showModal());
  });
  document.querySelectorAll('[data-close-import]').forEach((button) => {
    button.addEventListener('click', () => dialog?.close());
  });

  const technicalButton = document.querySelector('[data-toggle-technical]');
  technicalButton?.addEventListener('click', () => {
    document.body.classList.toggle('show-technical');
    technicalButton.textContent = document.body.classList.contains('show-technical')
      ? 'Ocultar detalles técnicos'
      : 'Mostrar detalles técnicos';
  });

  const filters = document.querySelectorAll('[data-alert-filters] button');
  const alertCards = document.querySelectorAll('[data-alert-card]');
  filters.forEach((button) => {
    button.addEventListener('click', () => {
      filters.forEach((item) => item.classList.remove('active'));
      button.classList.add('active');
      const severity = button.dataset.severity;
      alertCards.forEach((card) => {
        card.hidden = severity !== 'all' && card.dataset.severity !== severity;
      });
    });
  });

  const indicatorSearch = document.querySelector('[data-indicator-search]');
  indicatorSearch?.addEventListener('input', () => {
    const query = indicatorSearch.value.trim().toLocaleLowerCase('es');
    document.querySelectorAll('[data-indicator-card]').forEach((card) => {
      card.hidden = query && !card.dataset.search.toLocaleLowerCase('es').includes(query);
    });
  });

  const fileInput = document.querySelector('[data-import-file]');
  const profileField = document.querySelector('[data-profile-field]');
  const profileSelect = document.querySelector('[data-profile-select]');
  const xlsxGroup = document.querySelector('[data-xlsx-options]');
  const rowGroup = document.querySelector('[data-row-options]');
  const profileHelp = document.querySelector('[data-profile-help]');
  const rowValues = new Set(['products', 'customers', 'suppliers', 'sales', 'inventory', 'orders']);

  const updateProfileField = () => {
    const name = fileInput?.files?.[0]?.name || '';
    const extension = name.includes('.') ? `.${name.split('.').pop().toLowerCase()}` : '';
    const needsProfile = ['.xlsx', '.csv', '.tsv', '.json', '.ndjson', '.jsonl'].includes(extension);
    if (profileSelect) profileSelect.required = needsProfile;
    if (profileField) profileField.classList.toggle('optional', !needsProfile);
    if (profileHelp) {
      profileHelp.textContent = extension === '.xlsx'
        ? 'Selecciona el tipo de libro de Excel.'
        : needsProfile
          ? 'Selecciona qué tipo de registros contiene el archivo.'
          : 'Para documentos PDF, imágenes y XML no necesitas elegir.';
    }
    if (xlsxGroup) xlsxGroup.hidden = extension !== '.xlsx';
    if (rowGroup) rowGroup.hidden = extension === '.xlsx';
    if (profileSelect && extension === '.xlsx' && rowValues.has(profileSelect.value)) {
      profileSelect.value = '';
    }
  };
  fileInput?.addEventListener('change', updateProfileField);

  const importForm = document.querySelector('[data-import-form]');
  importForm?.addEventListener('submit', () => {
    const submit = document.querySelector('[data-import-submit]');
    const message = document.querySelector('[data-processing-message]');
    if (submit) {
      submit.disabled = true;
      submit.textContent = 'Actualizando…';
    }
    if (message) message.hidden = false;
  });
})();
