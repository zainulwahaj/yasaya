let globalScheduleData = [];
let currentPage = 1;
const rowsPerPage = 10;

// Limit how many page buttons we show
const maxPageButtons = 5;

document.getElementById('uploadForm').addEventListener('submit', function(e) {
  e.preventDefault();
  const formData = new FormData(e.target);

  // Show loader, hide old results
  document.getElementById('loader').style.display = 'block';
  document.getElementById('result').innerHTML = '';
  document.getElementById('downloadBtn').style.display = 'none';
  document.getElementById('paginationWrapper').style.display = 'none';
  document.getElementById('filterContainer').style.display = 'none';

  fetch('/upload', {
    method: 'POST',
    body: formData
  })
    .then(response => response.json())
    .then(data => {
      document.getElementById('loader').style.display = 'none';

      if (data.error) {
        document.getElementById('result').innerHTML = `<p class="error">${data.error}</p>`;
      } else {
        // Store entire schedule in global variable
        globalScheduleData = data.schedule;
        currentPage = 1;

        // Render table, pagination, and show filter + download
        displayTable(globalScheduleData, currentPage);
        setupPagination(globalScheduleData, rowsPerPage);
        document.getElementById('filterContainer').style.display = 'block';
        document.getElementById('downloadBtn').style.display = 'inline-block';
      }
    })
    .catch(error => {
      document.getElementById('loader').style.display = 'none';
      document.getElementById('result').innerHTML = `<p class="error">An error occurred: ${error}</p>`;
    });
});

// Download Excel
document.getElementById('downloadBtn').addEventListener('click', function() {
  // Simply go to /download_excel
  window.location.href = '/download_excel';
});

// Filter input
document.getElementById('filterInput').addEventListener('input', function(e) {
  const filterText = e.target.value.toLowerCase();

  // Filter across all columns
  const filteredData = globalScheduleData.filter(row =>
    Object.values(row).some(value =>
      value != null && String(value).toLowerCase().includes(filterText)
    )
  );

  currentPage = 1;
  displayTable(filteredData, currentPage);
  setupPagination(filteredData, rowsPerPage);
});

// Display table with pagination
function displayTable(data, page) {
  const start = (page - 1) * rowsPerPage;
  const end = start + rowsPerPage;
  const paginatedData = data.slice(start, end);

  if (paginatedData.length === 0) {
    document.getElementById('result').innerHTML = '<p>No schedule generated.</p>';
    return;
  }

  let html = '<h2>Generated Schedule</h2>';
  html += '<div class="table-responsive">';
  html += '<table class="schedule-table">';

  const headers = Object.keys(paginatedData[0]);
  html += '<thead><tr>';
  headers.forEach(header => {
    html += `<th>${header}</th>`;
  });
  html += '</tr></thead>';

  html += '<tbody>';
  paginatedData.forEach(row => {
    html += '<tr>';
    headers.forEach(header => {
      const cellValue = row[header] == null ? '' : row[header];
      html += `<td>${cellValue}</td>`;
    });
    html += '</tr>';
  });
  html += '</tbody></table></div>';

  document.getElementById('result').innerHTML = html;
}

function setupPagination(data, rowsPerPage) {
  const paginationEl = document.getElementById('pagination');
  const paginationInfoEl = document.getElementById('pagination-info');
  const paginationWrapper = document.getElementById('paginationWrapper');

  paginationEl.innerHTML = '';
  paginationInfoEl.innerHTML = '';

  const totalRecords = data.length;
  const pageCount = Math.ceil(totalRecords / rowsPerPage);

  // If no data or only one page, hide pagination
  if (pageCount <= 1) {
    paginationWrapper.style.display = 'none';
    return;
  } else {
    paginationWrapper.style.display = 'block';
  }

  // Display "Page X of Y"
  paginationInfoEl.textContent = `Page ${currentPage} of ${pageCount}`;

  // Prev Button
  const prevButton = document.createElement('button');
  prevButton.innerText = 'Prev';
  prevButton.classList.add('page-btn');
  prevButton.disabled = currentPage === 1;
  prevButton.addEventListener('click', () => {
    if (currentPage > 1) {
      currentPage--;
      displayTable(data, currentPage);
      setupPagination(data, rowsPerPage);
    }
  });
  paginationEl.appendChild(prevButton);

  // Determine which page buttons to show
  const half = Math.floor(maxPageButtons / 2);
  let startPage = currentPage - half;
  let endPage = currentPage + half;

  if (startPage < 1) {
    startPage = 1;
    endPage = Math.min(maxPageButtons, pageCount);
  }
  if (endPage > pageCount) {
    endPage = pageCount;
    startPage = Math.max(1, endPage - maxPageButtons + 1);
  }

  // If startPage > 1, show button for page 1, then '...'
  if (startPage > 1) {
    const firstPageBtn = document.createElement('button');
    firstPageBtn.innerText = '1';
    firstPageBtn.classList.add('page-btn');
    firstPageBtn.addEventListener('click', () => {
      currentPage = 1;
      displayTable(data, currentPage);
      setupPagination(data, rowsPerPage);
    });
    paginationEl.appendChild(firstPageBtn);

    if (startPage > 2) {
      const dots = document.createElement('span');
      dots.innerText = '...';
      dots.classList.add('dots');
      paginationEl.appendChild(dots);
    }
  }

  // Main numbered page buttons
  for (let i = startPage; i <= endPage; i++) {
    const pageButton = document.createElement('button');
    pageButton.innerText = i;
    pageButton.classList.add('page-btn');
    if (i === currentPage) {
      pageButton.classList.add('active');
    }
    pageButton.addEventListener('click', () => {
      currentPage = i;
      displayTable(data, currentPage);
      setupPagination(data, rowsPerPage);
    });
    paginationEl.appendChild(pageButton);
  }

  // If endPage < pageCount, show '...' and last page
  if (endPage < pageCount) {
    if (endPage < pageCount - 1) {
      const dots = document.createElement('span');
      dots.innerText = '...';
      dots.classList.add('dots');
      paginationEl.appendChild(dots);
    }

    const lastPageBtn = document.createElement('button');
    lastPageBtn.innerText = pageCount;
    lastPageBtn.classList.add('page-btn');
    lastPageBtn.addEventListener('click', () => {
      currentPage = pageCount;
      displayTable(data, currentPage);
      setupPagination(data, rowsPerPage);
    });
    paginationEl.appendChild(lastPageBtn);
  }

  // Next Button
  const nextButton = document.createElement('button');
  nextButton.innerText = 'Next';
  nextButton.classList.add('page-btn');
  nextButton.disabled = currentPage === pageCount;
  nextButton.addEventListener('click', () => {
    if (currentPage < pageCount) {
      currentPage++;
      displayTable(data, currentPage);
      setupPagination(data, rowsPerPage);
    }
  });
  paginationEl.appendChild(nextButton);
}
