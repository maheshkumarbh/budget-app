let currentAnalysis = null;
let currentTransactions = [];
let currentFileIds = [];
let currentPreview = null;
let transactionsPage = 1;
let transactionsPageSize = 50;
let categoryFilter = '';

// File upload handling
const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const fileList = document.getElementById('fileList');
const uploadSummary = document.getElementById('uploadSummary');
const manualForm = document.getElementById('manualForm');
const clearAllBtn = document.getElementById('clearAllBtn');
const backToUploadBtn = document.getElementById('backToUploadBtn');
const returnToResults = document.getElementById('returnToResults');
const viewResultsBtn = document.getElementById('viewResultsBtn');
const chooseFilesBtn = document.getElementById('chooseFilesBtn');
const deleteAllFilesBtn = document.getElementById('deleteAllFilesBtn');
const mappingSection = document.getElementById('mappingSection');
const statementType = document.getElementById('statementType');
const bankName = document.getElementById('bankName');
const mapDate = document.getElementById('mapDate');
const mapDescription = document.getElementById('mapDescription');
const mapAmount = document.getElementById('mapAmount');
const mapDebit = document.getElementById('mapDebit');
const mapCredit = document.getElementById('mapCredit');
const importBtn = document.getElementById('importBtn');
const previewHeaders = document.getElementById('previewHeaders');
const previewRows = document.getElementById('previewRows');
const prevPageBtn = document.getElementById('prevPageBtn');
const nextPageBtn = document.getElementById('nextPageBtn');
const pageSizeSelect = document.getElementById('pageSizeSelect');
const transactionsPageInfo = document.getElementById('transactionsPageInfo');
const categoryFilterSelect = document.getElementById('categoryFilter');
const categoryForm = document.getElementById('categoryForm');
const categoryNameInput = document.getElementById('categoryName');
const categoryKeywordsInput = document.getElementById('categoryKeywords');
const categoryList = document.getElementById('categoryList');

let customCategories = [];

// Drag and drop
uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
});

uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    handleFiles(e.dataTransfer.files);
});

uploadArea.addEventListener('click', () => {
    fileInput.value = '';
    fileInput.click();
});

if (chooseFilesBtn) {
    chooseFilesBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileInput.value = '';
        fileInput.click();
    });
}

fileInput.addEventListener('change', (e) => {
    handleFiles(e.target.files);
});

document.addEventListener('DOMContentLoaded', () => {
    initThemeToggle();
    loadExistingData();
    loadUploads();
    loadCategories();
});

function handleFiles(files) {
    if (files.length === 0) return;
    
    // Clear previous file list
    fileList.innerHTML = '';
    currentFileIds = [];
    currentPreview = null;
    if (mappingSection) {
        mappingSection.classList.add('hidden');
    }
    
    // Show selected files
    Array.from(files).forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'alert alert-info d-flex justify-content-between align-items-center';
        fileItem.dataset.index = String(index);
        fileItem.innerHTML = `
            <span><i class="fas fa-file"></i> ${file.name} (${formatFileSize(file.size)})</span>
            <div class="d-flex gap-2">
                <button class="btn btn-sm btn-outline-secondary" onclick="previewFileByIndex(${index})">Preview</button>
                <button class="btn btn-sm btn-danger" onclick="removeFile(this)">Remove</button>
            </div>
        `;
        fileList.appendChild(fileItem);
    });
    
    // Preview and mapping step
    previewFiles(files);
}

async function loadUploads() {
    try {
        const response = await fetch('/upload/list');
        const result = await response.json();
        renderUploadList(result.files || []);
    } catch (error) {
        // Best-effort
    }
}

function renderUploadList(files) {
    fileList.innerHTML = '';
    if (!files.length) {
        currentFileIds = [];
        return;
    }

    files.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'alert alert-info d-flex justify-content-between align-items-center';
        fileItem.dataset.index = String(index);
        fileItem.dataset.fileId = file.file_id;
        fileItem.innerHTML = `
            <span><i class="fas fa-file"></i> ${file.name}</span>
            <div class="d-flex gap-2">
                <button class="btn btn-sm btn-outline-secondary" onclick="previewFileByIndex(${index})">Preview</button>
                <button class="btn btn-sm btn-danger" onclick="removeFile(this)">Remove</button>
            </div>
        `;
        fileList.appendChild(fileItem);
    });

    currentFileIds = files.map(f => f.file_id);
}

if (deleteAllFilesBtn) {
    deleteAllFilesBtn.addEventListener('click', async () => {
        if (!confirm('Delete all uploaded files? This does not remove transactions.')) {
            return;
        }
        try {
            await fetch('/upload/cleanup-all', { method: 'POST' });
            loadUploads();
        } catch (error) {
            showError('Failed to delete files: ' + error.message);
        }
    });
}

function removeFile(button) {
    const item = button.closest('.alert');
    if (!item) return;
    const fileId = item.dataset.fileId;
    const index = parseInt(item.dataset.index || '-1', 10);
    item.remove();

    if (fileId) {
        cleanupUploads([fileId]);
        currentFileIds = currentFileIds.filter(id => id !== fileId);
    } else if (index >= 0 && currentFileIds[index]) {
        cleanupUploads([currentFileIds[index]]);
        currentFileIds = currentFileIds.filter((_, i) => i !== index);
    }

    if (fileList.children.length === 0) {
        if (mappingSection) {
            mappingSection.classList.add('hidden');
        }
        currentPreview = null;
        uploadSummary.innerHTML = '';
        currentFileIds = [];
    } else {
        // Re-sync indices and file ids so preview continues to work
        loadUploads();
    }
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

async function previewFiles(files) {
    showLoading();
    
    const formData = new FormData();
    Array.from(files).forEach(file => {
        formData.append('file', file);
    });
    
    try {
        const response = await fetch('/upload/preview', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            currentFileIds = result.file_ids || [];
            currentPreview = result.preview || null;
            syncFileIdsToList();
            showPreview(result);
        } else {
            showError(result.error || 'Upload failed');
        }
    } catch (error) {
        showError('Upload failed: ' + error.message);
    }
}

async function loadExistingData() {
    try {
        const response = await fetch('/transactions');
        const result = await response.json();
        if (result.transactions && result.transactions.length > 0) {
            currentTransactions = result.transactions;
            currentAnalysis = result.analysis;
            showResults();
        } else if (returnToResults) {
            returnToResults.classList.add('hidden');
        }
    } catch (error) {
        // Ignore on initial load
    }
}

async function loadCategories() {
    try {
        const response = await fetch('/categories');
        const result = await response.json();
        customCategories = result.categories || [];
        renderCategoryList();
        updateCategoryFilterOptions();
        updateManualCategoryOptions();
    } catch (error) {
        // Best-effort
    }
}

async function previewFileByIndex(index) {
    if (!currentFileIds || currentFileIds.length === 0) return;
    if (index < 0 || index >= currentFileIds.length) return;
    const fileId = currentFileIds[index];
    window.open(`/upload/view/${encodeURIComponent(fileId)}`, '_blank', 'noopener');
}

function syncFileIdsToList() {
    const items = Array.from(fileList.querySelectorAll('[data-index]'));
    items.forEach((item, idx) => {
        if (currentFileIds[idx]) {
            item.dataset.fileId = currentFileIds[idx];
        }
    });
}

function showUploadSummary(result) {
    if (!uploadSummary) return;
    const errors = (result.errors || []).map(e => `<li>${e}</li>`).join('');
    uploadSummary.innerHTML = `
        <div class="alert alert-info">
            Imported: ${result.imported || 0} transactions. Added: ${result.added || 0}. Skipped: ${result.skipped || 0}.
            ${errors ? `<ul class="mt-2 mb-0">${errors}</ul>` : ''}
        </div>
    `;
}

function showPreview(result) {
    document.getElementById('loadingSection').classList.add('hidden');
    document.getElementById('uploadSection').classList.remove('hidden');
    if (!mappingSection) return;
    mappingSection.classList.remove('hidden');

    const preview = result.preview || {};
    const columns = preview.columns || [];
    const suggested = preview.suggested_mapping || {};
    const rows = preview.sample_rows || [];

    populateSelect(mapDate, columns, suggested.date);
    populateSelect(mapDescription, columns, suggested.description);
    populateSelect(mapAmount, columns, suggested.amount);
    populateSelect(mapDebit, columns, suggested.debit);
    populateSelect(mapCredit, columns, suggested.credit);

    [mapDate, mapDescription, mapAmount, mapDebit, mapCredit].forEach(sel => {
        if (sel) sel.disabled = false;
    });
    if (previewHeaders && previewRows) {
        previewHeaders.innerHTML = columns.map(c => `<th>${c}</th>`).join('');
        previewRows.innerHTML = rows.map(row => {
            return `<tr>${columns.map(c => `<td>${row[c] ?? ''}</td>`).join('')}</tr>`;
        }).join('');
    }

    showUploadSummary(result);
}

function populateSelect(selectEl, columns, selected) {
    if (!selectEl) return;
    const options = [''].concat(columns);
    selectEl.innerHTML = options.map(c => {
        const label = c === '' ? '—' : c;
        const isSelected = selected && c === selected ? 'selected' : '';
        return `<option value="${c}" ${isSelected}>${label}</option>`;
    }).join('');
}

function showLoading() {
    document.getElementById('uploadSection').classList.add('hidden');
    document.getElementById('resultsSection').classList.add('hidden');
    document.getElementById('loadingSection').classList.remove('hidden');
}

function showError(message) {
    document.getElementById('loadingSection').classList.add('hidden');
    document.getElementById('uploadSection').classList.remove('hidden');
    
    const alert = document.createElement('div');
    alert.className = 'alert alert-danger alert-dismissible fade show';
    alert.innerHTML = `
        <i class="fas fa-exclamation-triangle"></i> ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    document.querySelector('.card-body').insertBefore(alert, document.querySelector('.upload-area'));
}

function showResults() {
    document.getElementById('loadingSection').classList.add('hidden');
    document.getElementById('uploadSection').classList.add('hidden');
    document.getElementById('resultsSection').classList.remove('hidden');
    if (returnToResults) {
        returnToResults.classList.remove('hidden');
    }
    
    updateSummaryCards();
    updateCharts();
    updateCategoryCards();
    updateRecommendations();
    updateCategoryFilterOptions();
    updateTransactionsTable();
}

function initThemeToggle() {
    const toggle = document.getElementById('themeToggle');
    if (!toggle) return;
    const stored = localStorage.getItem('theme');
    if (stored === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        toggle.querySelector('i').classList.remove('fa-moon');
        toggle.querySelector('i').classList.add('fa-sun');
    }
    toggle.addEventListener('click', () => {
        const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
        if (isDark) {
            document.documentElement.removeAttribute('data-theme');
            localStorage.setItem('theme', 'light');
            toggle.querySelector('i').classList.remove('fa-sun');
            toggle.querySelector('i').classList.add('fa-moon');
        } else {
            document.documentElement.setAttribute('data-theme', 'dark');
            localStorage.setItem('theme', 'dark');
            toggle.querySelector('i').classList.remove('fa-moon');
            toggle.querySelector('i').classList.add('fa-sun');
        }
    });
}

if (backToUploadBtn) {
    backToUploadBtn.addEventListener('click', () => {
        document.getElementById('resultsSection').classList.add('hidden');
        document.getElementById('uploadSection').classList.remove('hidden');
        if (returnToResults && currentTransactions.length > 0) {
            returnToResults.classList.remove('hidden');
        }
        loadUploads();
    });
}

if (viewResultsBtn) {
    viewResultsBtn.addEventListener('click', () => {
        if (currentTransactions.length > 0 && currentAnalysis) {
            showResults();
        }
    });
}

if (importBtn) {
    importBtn.addEventListener('click', async () => {
        if (!currentFileIds || currentFileIds.length === 0) {
            showError('No uploaded files to import.');
            return;
        }

        const mapping = {
            date: mapDate.value || null,
            description: mapDescription.value || null,
            amount: mapAmount.value || null,
            debit: mapDebit.value || null,
            credit: mapCredit.value || null
        };

        showLoading();
        try {
            const response = await fetch('/upload/commit', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    file_ids: currentFileIds,
                    mapping,
                    statement_type: statementType.value,
                    bank_name: bankName ? bankName.value.trim() : null
                })
            });
            const result = await response.json();
            if (result.success) {
                currentTransactions = result.transactions;
                currentAnalysis = result.analysis;
                if (mappingSection) {
                    mappingSection.classList.add('hidden');
                }
                showUploadSummary(result);
                showResults();
            } else {
                showError(result.error || 'Import failed');
            }
        } catch (error) {
            showError('Import failed: ' + error.message);
        }
    });
}

async function cleanupUploads(fileIds) {
    const ids = fileIds || currentFileIds;
    if (!ids || ids.length === 0) return;
    try {
        await fetch('/upload/cleanup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ file_ids: ids })
        });
        currentFileIds = [];
    } catch (error) {
        // Best-effort cleanup
    }
}


if (manualForm) {
    manualForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const date = document.getElementById('manualDate').value;
        const type = document.getElementById('manualType').value;
        const amountInput = parseFloat(document.getElementById('manualAmount').value || '0');
        const description = document.getElementById('manualDescription').value;
        const category = document.getElementById('manualCategory').value || null;

        if (!date || !description || !amountInput) {
            showError('Date, description, and amount are required.');
            return;
        }

        const amount = type === 'expense' ? -Math.abs(amountInput) : Math.abs(amountInput);

        try {
            const response = await fetch('/transactions', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ date, description, amount, category })
            });

            const result = await response.json();
            if (result.success) {
                currentTransactions = result.transactions;
                currentAnalysis = result.analysis;
                manualForm.reset();
                showResults();
            } else {
                showError(result.error || 'Failed to add transaction');
            }
        } catch (error) {
            showError('Failed to add transaction: ' + error.message);
        }
    });
}

if (clearAllBtn) {
    clearAllBtn.addEventListener('click', async () => {
        if (!confirm('This will delete all stored transactions. Continue?')) {
            return;
        }
        try {
            await fetch('/transactions/clear', { method: 'POST' });
            currentTransactions = [];
            currentAnalysis = null;
            document.getElementById('resultsSection').classList.add('hidden');
            document.getElementById('uploadSection').classList.remove('hidden');
            if (returnToResults) {
                returnToResults.classList.add('hidden');
            }
        } catch (error) {
            showError('Failed to clear data: ' + error.message);
        }
    });
}

function updateSummaryCards() {
    const totalExpenses = currentAnalysis.total_expenses;
    const categories = Object.keys(currentAnalysis.category_breakdown).length;
    const potentialSavings = currentAnalysis.recommendations.reduce((sum, rec) => sum + rec.potential_savings, 0);
    const transactionCount = currentTransactions.length;
    
    document.getElementById('totalExpenses').textContent = `$${totalExpenses.toFixed(2)}`;
    document.getElementById('categoryCount').textContent = categories;
    document.getElementById('potentialSavings').textContent = `$${potentialSavings.toFixed(2)}`;
    document.getElementById('transactionCount').textContent = transactionCount;
}

function updateCharts() {
    // Category breakdown pie chart
    const categoryData = [{
        values: Object.values(currentAnalysis.category_breakdown),
        labels: Object.keys(currentAnalysis.category_breakdown).map(cat => cat.charAt(0).toUpperCase() + cat.slice(1)),
        type: 'pie',
        marker: {
            colors: ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', '#DDA0DD', '#98D8C8', '#F7DC6F', '#F8B739', '#85C1E9']
        }
    }];
    
    const categoryLayout = {
        title: 'Expenses by Category',
        font: { size: 14 }
    };
    
    Plotly.newPlot('categoryChart', categoryData, categoryLayout, {responsive: true});
    
    // Monthly trends line chart
    const months = Object.keys(currentAnalysis.monthly_trends).sort();
    const categories = [...new Set(currentTransactions.map(t => t.category))];
    
    const trendData = categories.map(category => {
        const monthlyValues = months.map(month => 
            currentAnalysis.monthly_trends[month][category] || 0
        );
        
        return {
            x: months,
            y: monthlyValues,
            type: 'scatter',
            mode: 'lines+markers',
            name: category.charAt(0).toUpperCase() + category.slice(1),
            stackgroup: 'one'
        };
    });
    
    const trendLayout = {
        title: 'Monthly Expense Trends',
        xaxis: { title: 'Month' },
        yaxis: { title: 'Amount ($)' },
        font: { size: 14 }
    };
    
    Plotly.newPlot('trendChart', trendData, trendLayout, {responsive: true});
}

function updateCategoryCards() {
    const categoryCards = document.getElementById('categoryCards');
    categoryCards.innerHTML = '';
    
    Object.entries(currentAnalysis.category_breakdown).forEach(([category, amount]) => {
        const percentage = ((amount / currentAnalysis.total_expenses) * 100).toFixed(1);
        const icon = getCategoryIcon(category);
        const color = getCategoryColor(category);
        
        const card = document.createElement('div');
        card.className = 'col-md-4 mb-3';
        card.innerHTML = `
            <div class="card expense-card" style="border-left-color: ${color}">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <i class="${icon} category-icon" style="color: ${color}"></i>
                            <h5>${category.charAt(0).toUpperCase() + category.slice(1)}</h5>
                            <h4 class="text-primary">$${amount.toFixed(2)}</h4>
                            <small class="text-muted">${percentage}% of total</small>
                        </div>
                        <div>
                            <div class="progress" style="width: 60px; height: 6px;">
                                <div class="progress-bar" role="progressbar" 
                                     style="width: ${percentage}%; background-color: ${color}"
                                     aria-valuenow="${percentage}" aria-valuemin="0" aria-valuemax="100"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
        categoryCards.appendChild(card);
    });
}

function updateRecommendations() {
    const recommendationsList = document.getElementById('recommendationsList');
    recommendationsList.innerHTML = '';
    
    if (currentAnalysis.recommendations.length === 0) {
        recommendationsList.innerHTML = `
            <div class="alert alert-success">
                <i class="fas fa-check-circle"></i> Great job! Your expenses look well-balanced.
            </div>
        `;
        return;
    }
    
    currentAnalysis.recommendations.forEach((rec, index) => {
        const priorityClass = rec.priority === 'high' ? 'recommendation-high' : 
                             rec.priority === 'medium' ? 'recommendation-medium' : 'recommendation-low';
        
        const recommendation = document.createElement('div');
        recommendation.className = `card expense-card mb-3 ${priorityClass}`;
        recommendation.innerHTML = `
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-start">
                    <div>
                        <h5>
                            <i class="fas fa-lightbulb text-warning"></i> 
                            ${rec.category.charAt(0).toUpperCase() + rec.category.slice(1)} Optimization
                        </h5>
                        <p>${rec.message}</p>
                        <div class="mt-2">
                            <span class="badge bg-${rec.priority === 'high' ? 'danger' : rec.priority === 'medium' ? 'warning' : 'success'}">
                                ${rec.priority.toUpperCase()} PRIORITY
                            </span>
                        </div>
                    </div>
                    <div class="text-end">
                        <h4 class="text-success">$${rec.potential_savings.toFixed(2)}</h4>
                        <small class="text-muted">Potential savings</small>
                    </div>
                </div>
            </div>
        `;
        recommendationsList.appendChild(recommendation);
    });
}

function updateTransactionsTable() {
    const tbody = document.getElementById('transactionsTable');
    tbody.innerHTML = '';
    
    let expenses = currentTransactions
        .filter(t => t.amount < 0)
        .sort((a, b) => new Date(b.date) - new Date(a.date));

    if (categoryFilter) {
        expenses = expenses.filter(t => (t.category || '') === categoryFilter);
    }

    const total = expenses.length;
    const totalPages = Math.max(1, Math.ceil(total / transactionsPageSize));
    if (transactionsPage > totalPages) {
        transactionsPage = totalPages;
    }
    const start = (transactionsPage - 1) * transactionsPageSize;
    const end = start + transactionsPageSize;
    const pageRows = expenses.slice(start, end);

    if (transactionsPageInfo) {
        const shownStart = total === 0 ? 0 : start + 1;
        const shownEnd = Math.min(end, total);
        transactionsPageInfo.textContent = `Showing ${shownStart}-${shownEnd} of ${total}`;
    }
    if (prevPageBtn) prevPageBtn.disabled = transactionsPage <= 1;
    if (nextPageBtn) nextPageBtn.disabled = transactionsPage >= totalPages;
    
    pageRows.forEach(transaction => {
        const baseOptions = [
            'food', 'transport', 'shopping', 'entertainment', 'utilities',
            'healthcare', 'housing', 'education', 'subscriptions', 'cash', 'other', 'income'
        ];
        const customOptions = customCategories.map(c => c.name.toLowerCase());
        const categoryOptions = [''].concat([...new Set(baseOptions.concat(customOptions))]);
        const currentCategory = transaction.category || '';
        const categorySelect = `
            <select class="form-select form-select-sm" onchange="updateCategory(${transaction.id}, this.value)">
                ${categoryOptions.map(cat => {
                    const label = cat === '' ? 'Auto' : cat;
                    const selected = currentCategory === cat ? 'selected' : '';
                    return `<option value="${cat}" ${selected}>${label}</option>`;
                }).join('')}
            </select>
        `;
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${transaction.date}</td>
            <td>${transaction.description}</td>
            <td>${categorySelect}</td>
            <td class="text-danger">-$${Math.abs(transaction.amount).toFixed(2)}</td>
            <td class="text-end">
                <button class="btn btn-sm btn-outline-danger" onclick="deleteTransaction(${transaction.id})">Delete</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function updateCategoryFilterOptions() {
    if (!categoryFilterSelect) return;
    const baseCats = currentTransactions
        .filter(t => t.amount < 0)
        .map(t => t.category || 'other');
    const customCats = customCategories.map(c => c.name.toLowerCase());
    const categories = Array.from(new Set(baseCats.concat(customCats))).sort();

    const options = [''].concat(categories);
    categoryFilterSelect.innerHTML = options.map(c => {
        const label = c === '' ? 'All categories' : c;
        const selected = c === categoryFilter ? 'selected' : '';
        return `<option value="${c}" ${selected}>${label}</option>`;
    }).join('');
}

function updateManualCategoryOptions() {
    const select = document.getElementById('manualCategory');
    if (!select) return;
    const base = [
        'food', 'transport', 'shopping', 'entertainment', 'utilities',
        'healthcare', 'housing', 'education', 'subscriptions', 'cash', 'other'
    ];
    const custom = customCategories.map(c => c.name.toLowerCase());
    const options = [''].concat([...new Set(base.concat(custom))]);
    select.innerHTML = options.map(c => {
        const label = c === '' ? 'Auto' : c;
        return `<option value="${c}">${label}</option>`;
    }).join('');
}

function renderCategoryList() {
    if (!categoryList) return;
    if (!customCategories.length) {
        categoryList.innerHTML = '<div class="muted small">No custom categories yet.</div>';
        return;
    }
    categoryList.innerHTML = customCategories.map(c => `
        <div class="alert alert-light d-flex justify-content-between align-items-center">
            <div>
                <strong>${c.name}</strong>
                <div class="muted small">${c.keywords}</div>
            </div>
            <button class="btn btn-sm btn-outline-danger" onclick="deleteCategory(${c.id})">Delete</button>
        </div>
    `).join('');
}

if (categoryFilterSelect) {
    categoryFilterSelect.addEventListener('change', (e) => {
        categoryFilter = e.target.value;
        transactionsPage = 1;
        updateTransactionsTable();
    });
}

if (categoryForm) {
    categoryForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const name = categoryNameInput.value.trim();
        const keywords = categoryKeywordsInput.value.trim();
        if (!name || !keywords) {
            showError('Category name and keywords are required.');
            return;
        }
        try {
            const response = await fetch('/categories', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, keywords })
            });
            const result = await response.json();
            if (result.success) {
                customCategories = result.categories || [];
                categoryNameInput.value = '';
                categoryKeywordsInput.value = '';
                renderCategoryList();
                updateManualCategoryOptions();
                updateCategoryFilterOptions();
                // Re-run analysis using updated categories
                loadExistingData();
            } else {
                showError(result.error || 'Failed to add category');
            }
        } catch (error) {
            showError('Failed to add category: ' + error.message);
        }
    });
}

async function deleteCategory(id) {
    if (!confirm('Delete this category rule?')) return;
    try {
        const response = await fetch(`/categories/${id}`, { method: 'DELETE' });
        const result = await response.json();
        customCategories = result.categories || [];
        renderCategoryList();
        updateManualCategoryOptions();
        updateCategoryFilterOptions();
        loadExistingData();
    } catch (error) {
        showError('Failed to delete category: ' + error.message);
    }
}

if (prevPageBtn) {
    prevPageBtn.addEventListener('click', () => {
        if (transactionsPage > 1) {
            transactionsPage -= 1;
            updateTransactionsTable();
        }
    });
}

if (nextPageBtn) {
    nextPageBtn.addEventListener('click', () => {
        transactionsPage += 1;
        updateTransactionsTable();
    });
}

if (pageSizeSelect) {
    pageSizeSelect.addEventListener('change', (e) => {
        transactionsPageSize = parseInt(e.target.value, 10) || 50;
        transactionsPage = 1;
        updateTransactionsTable();
    });
}

async function updateCategory(txnId, category) {
    try {
        const response = await fetch(`/transactions/${txnId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ category })
        });
        const result = await response.json();
        if (result.success) {
            currentTransactions = result.transactions;
            currentAnalysis = result.analysis;
            showResults();
        } else {
            showError(result.error || 'Failed to update category');
        }
    } catch (error) {
        showError('Failed to update category: ' + error.message);
    }
}
async function deleteTransaction(txnId) {
    if (!confirm('Delete this transaction?')) {
        return;
    }
    try {
        const response = await fetch(`/transactions/${txnId}`, { method: 'DELETE' });
        const result = await response.json();
        if (result.success) {
            currentTransactions = result.transactions;
            currentAnalysis = result.analysis;
            showResults();
        } else {
            showError('Failed to delete transaction');
        }
    } catch (error) {
        showError('Failed to delete transaction: ' + error.message);
    }
}

function getCategoryIcon(category) {
    const icons = {
        'food': 'fas fa-utensils',
        'transport': 'fas fa-car',
        'shopping': 'fas fa-shopping-cart',
        'entertainment': 'fas fa-film',
        'utilities': 'fas fa-bolt',
        'healthcare': 'fas fa-heartbeat',
        'housing': 'fas fa-home',
        'education': 'fas fa-graduation-cap',
        'subscriptions': 'fas fa-sync',
        'cash': 'fas fa-money-bill',
        'other': 'fas fa-ellipsis-h',
        'income': 'fas fa-plus-circle'
    };
    return icons[category] || icons.other;
}

function getCategoryColor(category) {
    const colors = {
        'food': '#FF6B6B',
        'transport': '#4ECDC4',
        'shopping': '#45B7D1',
        'entertainment': '#96CEB4',
        'utilities': '#FFEAA7',
        'healthcare': '#DDA0DD',
        'housing': '#98D8C8',
        'education': '#A78BFA',
        'subscriptions': '#F7DC6F',
        'cash': '#F8B739',
        'other': '#85C1E9',
        'income': '#2ECC71'
    };
    return colors[category] || colors.other;
}
