// Real client-side interactivity for the mock financial data-center pages.
// No backend participation: clicking a header really re-sorts the DOM rows,
// clicking a tab/chip really hides/shows rows. Row `id` attributes never
// change across sort/filter, so a live DOM query for a known row id always
// returns that row's *current* on-screen position.

function cellValueAt(row, colIndex, type) {
  const cell = row.children[colIndex];
  if (!cell) return type === 'number' ? -Infinity : '';
  const raw = cell.dataset.value !== undefined ? cell.dataset.value : cell.textContent.trim();
  if (type === 'number') {
    const n = parseFloat(String(raw).replace(/[^0-9.\-]/g, ''));
    return Number.isNaN(n) ? -Infinity : n;
  }
  return String(raw);
}

function recomputeRank(table) {
  const rows = Array.from(table.querySelectorAll('tbody tr'));
  let visible = 0;
  rows.forEach((tr) => {
    const rc = tr.querySelector('td.rank-cell');
    if (tr.classList.contains('row-hidden')) return;
    visible += 1;
    if (rc) rc.textContent = String(visible);
  });
}

function attachSortableTable(table) {
  const headers = Array.from(table.querySelectorAll('thead th[data-sort]'));
  headers.forEach((th) => {
    th.addEventListener('click', () => {
      const allTh = Array.from(th.parentElement.children);
      const colIndex = allTh.indexOf(th);
      const type = th.dataset.type || 'number';
      const currentDir = th.dataset.dir || '';
      const nextDir = currentDir === 'asc' ? 'desc' : 'asc';

      allTh.forEach((h) => {
        if (h === th) return;
        delete h.dataset.dir;
        const ic = h.querySelector('.sort-ico');
        if (ic) ic.textContent = '\u21C5';
      });
      th.dataset.dir = nextDir;
      const ic = th.querySelector('.sort-ico');
      if (ic) ic.textContent = nextDir === 'asc' ? '\u25B2' : '\u25BC';

      const tbody = table.querySelector('tbody');
      const rows = Array.from(tbody.querySelectorAll('tr'));
      rows.sort((r1, r2) => {
        const v1 = cellValueAt(r1, colIndex, type);
        const v2 = cellValueAt(r2, colIndex, type);
        if (v1 < v2) return nextDir === 'asc' ? -1 : 1;
        if (v1 > v2) return nextDir === 'asc' ? 1 : -1;
        return 0;
      });
      rows.forEach((r) => tbody.appendChild(r));
      recomputeRank(table);
    });
  });
}

// Two kinds of filter controls:
//  - "radio" group (e.g. board tabs): only one chip active at a time, row
//    must match the active chip's `data-filter` value on the row's
//    `data-board` attribute (special value "all" clears the filter).
//  - "threshold" chips (e.g. "connect-streak >= 3 days"): independently
//    toggleable, AND-combined — a row must satisfy every active chip.
function attachFilterChips(root, table) {
  const chips = Array.from(root.querySelectorAll('[data-filter]'));
  chips.forEach((chip) => {
    chip.addEventListener('click', () => {
      if (chip.dataset.filterGroup === 'radio') {
        Array.from(chip.parentElement.children).forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
      } else {
        chip.classList.toggle('active');
      }
      applyFilters(root, table);
    });
  });
  applyFilters(root, table);
}

function applyFilters(root, table) {
  const activeChips = Array.from(root.querySelectorAll('[data-filter].active'));
  const radioChip = activeChips.find((c) => c.dataset.filterGroup === 'radio');
  const thresholdChips = activeChips.filter((c) => c.dataset.filterGroup !== 'radio');

  const rows = Array.from(table.querySelectorAll('tbody tr'));
  rows.forEach((tr) => {
    let visible = true;

    if (radioChip && radioChip.dataset.filter !== 'all') {
      visible = visible && tr.dataset.board === radioChip.dataset.filter;
    }

    thresholdChips.forEach((chip) => {
      const attr = chip.dataset.filterAttr;
      const min = parseFloat(chip.dataset.filterMin);
      const val = parseFloat(tr.dataset[attr] || '');
      if (!(val >= min)) visible = false;
    });

    tr.classList.toggle('row-hidden', !visible);
  });
  recomputeRank(table);
}

function initPage(tableSelector) {
  const table = document.querySelector(tableSelector);
  if (!table) return;
  attachSortableTable(table);
  const filterRoot = document.querySelector('[data-filter-root]');
  if (filterRoot) attachFilterChips(filterRoot, table);
  recomputeRank(table);
}

document.addEventListener('DOMContentLoaded', () => {
  const table = document.querySelector('table[data-page-table]');
  if (table) initPage('table[data-page-table]');
});
