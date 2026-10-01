// Global State
let glFileSelected = false;
let bankFileSelected = false;
let statusChart = null;

// API Base URL
const API_URL = 'http://localhost:5000/api';

// Tab Navigation
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        const tabName = btn.dataset.tab;
        switchTab(tabName);
    });
});

function switchTab(tabName) {
    // Hide all tabs
    document.querySelectorAll('.tab-content').forEach(tab => {
        tab.classList.remove('active');
    });

    // Remove active class from all buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });

    // Show selected tab
    document.getElementById(tabName).classList.add('active');

    // Add active class to button
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Load data if needed
    if (tabName === 'dashboard') {
        loadSummary();
    } else if (tabName === 'matches') {
        loadMatches();
    } else if (tabName === 'exceptions') {
        loadExceptions();
    }
}

// File Upload Handlers
document.getElementById('glFile').addEventListener('change', function() {
    glFileSelected = !!this.files.length;
    document.getElementById('uploadGLBtn').disabled = !glFileSelected;
});

document.getElementById('bankFile').addEventListener('change', function() {
    bankFileSelected = !!this.files.length;
    document.getElementById('uploadBankBtn').disabled = !bankFileSelected;
});

// Drag and drop
['glFile', 'bankFile'].forEach(fileInputId => {
    const fileInput = document.getElementById(fileInputId);
    const label = fileInput.nextElementSibling;

    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        label.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    label.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        fileInput.files = files;
        fileInput.dispatchEvent(new Event('change'));
    });
});

// Upload GL Button
document.getElementById('uploadGLBtn').addEventListener('click', async () => {
    const file = document.getElementById('glFile').files[0];
    if (!file) {
        showToast('Please select a file', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_URL}/upload-gl`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            showStatus('glStatus', `✅ ${data.message}`, 'success');
            showToast(`GL Data Uploaded: ${data.count} entries`, 'success');
        } else {
            showStatus('glStatus', `❌ ${data.error}`, 'error');
            showToast(data.error, 'error');
        }
    } catch (error) {
        showStatus('glStatus', `❌ ${error.message}`, 'error');
        showToast(error.message, 'error');
    }
});

// Upload Bank Button
document.getElementById('uploadBankBtn').addEventListener('click', async () => {
    const file = document.getElementById('bankFile').files[0];
    if (!file) {
        showToast('Please select a file', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`${API_URL}/upload-bank`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (response.ok) {
            showStatus('bankStatus', `✅ ${data.message}`, 'success');
            showToast(`Bank Data Uploaded: ${data.count} entries`, 'success');
        } else {
            showStatus('bankStatus', `❌ ${data.error}`, 'error');
            showToast(data.error, 'error');
        }
    } catch (error) {
        showStatus('bankStatus', `❌ ${error.message}`, 'error');
        showToast(error.message, 'error');
    }
});

// Reconcile Button
document.getElementById('reconcileBtn').addEventListener('click', async () => {
    const tolerance = parseFloat(document.getElementById('tolerance').value) / 100;

    try {
        showStatus('reconcileStatus', '⏳ Running reconciliation...', 'info');
        document.getElementById('reconcileBtn').disabled = true;

        const response = await fetch(`${API_URL}/reconcile`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ tolerance })
        });

        const data = await response.json();

        if (response.ok) {
            document.getElementById('matchedCount').textContent = data.matched;
            document.getElementById('unmatchedGLCount').textContent = data.unmatched_gl;
            document.getElementById('unmatchedBankCount').textContent = data.unmatched_bank;
            document.getElementById('matchRate').textContent = data.match_rate + '%';

            document.getElementById('reconcileResults').style.display = 'block';
            showStatus('reconcileStatus', `✅ Reconciliation complete! ${data.matched} entries matched.`, 'success');
            showToast('Reconciliation completed successfully!', 'success');
        } else {
            showStatus('reconcileStatus', `❌ ${data.error}`, 'error');
            showToast(data.error, 'error');
        }
    } catch (error) {
        showStatus('reconcileStatus', `❌ ${error.message}`, 'error');
        showToast(error.message, 'error');
    } finally {
        document.getElementById('reconcileBtn').disabled = false;
    }
});

// Load Summary
async function loadSummary() {
    try {
        const response = await fetch(`${API_URL}/summary`);
        const data = await response.json();

        document.getElementById('statGLEntries').textContent = data.gl_entries;
        document.getElementById('statBankEntries').textContent = data.bank_entries;
        document.getElementById('statMatched').textContent = data.matched_entries;
        document.getElementById('statExceptions').textContent = data.open_exceptions;

        // Update chart
        updateStatusChart(
            data.matched_entries,
            data.gl_entries - data.matched_entries,
            data.bank_entries - data.matched_entries
        );
    } catch (error) {
        console.error('Error loading summary:', error);
    }
}

// Load Matches
async function loadMatches() {
    try {
        const response = await fetch(`${API_URL}/matches`);
        const matches = await response.json();

        const tbody = document.getElementById('matchesTbody');
        tbody.innerHTML = '';

        if (matches.length === 0) {
            tbody.innerHTML = '<tr class="empty"><td colspan="9">No matched entries yet.</td></tr>';
            return;
        }

        matches.forEach(match => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${match.match_type}</td>
                <td><strong>${(match.confidence_score * 100).toFixed(1)}%</strong></td>
                <td>${formatDate(match.gl_date)}</td>
                <td>${formatDate(match.bank_date)}</td>
                <td>${formatCurrency(match.debit - match.credit)}</td>
                <td>${formatCurrency(match.amount)}</td>
                <td>${formatCurrency(match.debit - match.credit - match.amount)}</td>
                <td>${match.gl_desc}</td>
                <td>${match.bank_desc}</td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading matches:', error);
    }
}

// Load Exceptions
async function loadExceptions() {
    try {
        const response = await fetch(`${API_URL}/exceptions`);
        const exceptions = await response.json();

        const tbody = document.getElementById('exceptionsTbody');
        tbody.innerHTML = '';

        if (exceptions.length === 0) {
            tbody.innerHTML = '<tr class="empty"><td colspan="7">All entries matched! No exceptions.</td></tr>';
            return;
        }

        exceptions.forEach(exc => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${exc.entry_type}</td>
                <td>${exc.exception_type}</td>
                <td>${formatCurrency(exc.amount)}</td>
                <td>${exc.description}</td>
                <td>${formatDate(exc.created_at)}</td>
                <td><span class="status-badge ${exc.status.toLowerCase()}">${exc.status}</span></td>
                <td>
                    <button class="btn btn-danger" onclick="resolveException(${exc.id})">Resolve</button>
                </td>
            `;
            tbody.appendChild(row);
        });
    } catch (error) {
        console.error('Error loading exceptions:', error);
    }
}

// Resolve Exception
async function resolveException(excId) {
    try {
        const response = await fetch(`${API_URL}/exceptions/${excId}/resolve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ resolution: 'Marked as resolved' })
        });

        if (response.ok) {
            showToast('Exception resolved', 'success');
            loadExceptions();
        } else {
            showToast('Error resolving exception', 'error');
        }
    } catch (error) {
        showToast(error.message, 'error');
    }
}

// Update Status Chart
function updateStatusChart(matched, unmatchedGL, unmatchedBank) {
    const ctx = document.getElementById('statusChart');
    
    if (statusChart) {
        statusChart.destroy();
    }

    statusChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Matched', 'Unmatched GL', 'Unmatched Bank'],
            datasets: [{
                data: [matched, unmatchedGL, unmatchedBank],
                backgroundColor: ['#10b981', '#ef4444', '#f59e0b'],
                borderColor: ['#059669', '#dc2626', '#d97706'],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

// Export Report
document.getElementById('exportBtn').addEventListener('click', async () => {
    try {
        const response = await fetch(`${API_URL}/export-report`);
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `Reconciliation_Report_${new Date().toISOString().slice(0, 10)}.xlsx`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            showToast('Report exported successfully', 'success');
        }
    } catch (error) {
        showToast('Error exporting report: ' + error.message, 'error');
    }
});

// Refresh Button
document.getElementById('refreshBtn').addEventListener('click', () => {
    loadSummary();
    showToast('Data refreshed', 'success');
});

// Download Sample Files
document.getElementById('downloadGLSample').addEventListener('click', () => {
    const sampleData = `date,account_code,description,debit,credit,reference
2024-01-15,1000,Sale Invoice INV001,5000,0,INV001
2024-01-15,1200,Service Income,3000,0,SVC001
2024-01-16,2000,Expense Payment,0,2000,CHK001
2024-01-17,1000,Refund Issued,0,500,REF001
2024-01-18,1200,Income Adjustment,1500,0,ADJ001`;

    downloadFile(sampleData, 'GL_Sample.csv');
});

document.getElementById('downloadBankSample').addEventListener('click', () => {
    const sampleData = `date,amount,description,reference,bank_reference
2024-01-15,5000,Deposit - INV001,INV001,TXN123456
2024-01-15,3000,Deposit - SVC001,SVC001,TXN123457
2024-01-16,-2000,Check Payment,CHK001,TXN123458
2024-01-17,-500,Refund Processed,REF001,TXN123459
2024-01-18,1500,Income Deposit,ADJ001,TXN123460`;

    downloadFile(sampleData, 'Bank_Sample.csv');
});

function downloadFile(content, filename) {
    const element = document.createElement('a');
    element.setAttribute('href', 'data:text/csv;charset=utf-8,' + encodeURIComponent(content));
    element.setAttribute('download', filename);
    element.style.display = 'none';
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
}

// Utility Functions
function showStatus(elementId, message, type) {
    const element = document.getElementById(elementId);
    element.textContent = message;
    element.className = `status show ${type}`;
}

function showToast(message, type = 'info') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast show ${type}`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

function formatCurrency(amount) {
    return new Intl.NumberFormat('en-US', {
        style: 'currency',
        currency: 'INR'
    }).format(amount);
}

function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Initial load
document.addEventListener('DOMContentLoaded', () => {
    loadSummary();
});
