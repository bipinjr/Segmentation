/**
 * CustomerIQ — Customer Segmentation & Intelligence Platform
 * Frontend Application Controller
 * Handles REST API communication, Plotly.js charts, interactive filtering,
 * theme management, and modal interactions.
 */

// Application State
const state = {
    theme: localStorage.getItem("customeriq_theme") || "light",
    mode: "segmentation", // "segmentation" | "clean-only"
    activeTab: "dashboard",
    pipelineResults: null,
    customers: {
        page: 1,
        perPage: 15,
        search: "",
        segment: "all",
        sortBy: "Monetary",
        sortOrder: "desc",
        total: 0,
        totalPages: 1
    },
    cleanOnly: {
        page: 1,
        perPage: 15,
        search: "",
        sortBy: "InvoiceDate",
        sortOrder: "desc",
        total: 0,
        totalPages: 1,
        previewLimit: 10,
        report: null
    },
    colors: {
        VIP: "#10b981",
        Regular: "#3b82f6",
        Rare: "#f59e0b",
        Loyal: "#6366f1",
        Promising: "#06b6d4",
        "At-Risk": "#ec4899",
        Hibernating: "#8b5cf6",
        Lost: "#ef4444"
    }
};

// DOM Content Loaded
document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initNavigation();
    initCleanOnlyMode();
    initUploadModal();
    initCustomerExplorer();
    initTuningForm();
    initActionButtons();

    // Initial system load
    loadInitialData();
});

// ---------------------------------------------------------------- Theme Controller
function initTheme() {
    document.documentElement.setAttribute("data-theme", state.theme);
    const themeBtn = document.getElementById("themeToggleBtn");
    if (themeBtn) {
        themeBtn.addEventListener("click", () => {
            state.theme = state.theme === "light" ? "dark" : "light";
            document.documentElement.setAttribute("data-theme", state.theme);
            localStorage.setItem("customeriq_theme", state.theme);
            // Re-render charts with updated theme colors
            if (state.pipelineResults) {
                renderAllCharts(state.pipelineResults);
            }
        });
    }
}

function getPlotlyThemeLayout() {
    const isDark = state.theme === "dark";
    return {
        paper_bgcolor: isDark ? "#111827" : "#ffffff",
        plot_bgcolor: isDark ? "#111827" : "#ffffff",
        font: {
            color: isDark ? "#94a3b8" : "#475569",
            family: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
            size: 11
        },
        margin: { t: 30, r: 25, l: 45, b: 40 }
    };
}

// ---------------------------------------------------------------- Navigation & Tabs
function initNavigation() {
    const navItems = document.querySelectorAll(".nav-item");
    const mobileMenuBtn = document.getElementById("mobileMenuBtn");
    const mobileCloseBtn = document.getElementById("mobileCloseBtn");
    const sidebar = document.getElementById("sidebar");

    // Mode Switcher buttons
    const btnModeSegmentation = document.getElementById("btnModeSegmentation");
    const btnModeCleanOnly = document.getElementById("btnModeCleanOnly");

    btnModeSegmentation?.addEventListener("click", () => setPlatformMode("segmentation"));
    btnModeCleanOnly?.addEventListener("click", () => setPlatformMode("clean-only"));

    navItems.forEach(item => {
        item.addEventListener("click", (e) => {
            e.preventDefault();
            const tabId = item.getAttribute("data-tab");
            const scrollTarget = item.getAttribute("data-scroll");

            if (tabId) {
                switchTab(tabId);
            } else if (scrollTarget) {
                const el = document.getElementById(scrollTarget);
                if (el) {
                    el.scrollIntoView({ behavior: "smooth", block: "start" });
                }
                document.querySelectorAll("#sidebarNavCleanOnly .nav-item").forEach(i => i.classList.remove("active"));
                item.classList.add("active");
            }

            if (sidebar.classList.contains("open")) {
                sidebar.classList.remove("open");
            }
        });
    });

    if (mobileMenuBtn && sidebar) {
        mobileMenuBtn.addEventListener("click", () => sidebar.classList.add("open"));
    }
    if (mobileCloseBtn && sidebar) {
        mobileCloseBtn.addEventListener("click", () => sidebar.classList.remove("open"));
    }

    // Hash navigation support
    window.addEventListener("hashchange", () => {
        const hash = window.location.hash.replace("#", "");
        if (hash === "clean-only") {
            setPlatformMode("clean-only");
        } else if (hash) {
            setPlatformMode("segmentation");
            switchTab(hash);
        }
    });
}

function setPlatformMode(mode) {
    state.mode = mode;
    const btnSeg = document.getElementById("btnModeSegmentation");
    const btnClean = document.getElementById("btnModeCleanOnly");
    const navSeg = document.getElementById("sidebarNavSegmentation");
    const navClean = document.getElementById("sidebarNavCleanOnly");
    const tabClean = document.getElementById("tab-clean-only");

    if (mode === "clean-only") {
        btnClean?.classList.add("active");
        btnSeg?.classList.remove("active");
        if (navSeg) navSeg.style.display = "none";
        if (navClean) navClean.style.display = "flex";

        // Hide segmentation tabs and show clean data workspace
        document.querySelectorAll(".tab-pane").forEach(pane => pane.classList.remove("active"));
        if (tabClean) tabClean.classList.add("active");

        // Load preview and anomalies
        loadCleanOnlyPreview();
        loadCleanedRows(1);
    } else {
        btnSeg?.classList.add("active");
        btnClean?.classList.remove("active");
        if (navSeg) navSeg.style.display = "flex";
        if (navClean) navClean.style.display = "none";

        if (tabClean) tabClean.classList.remove("active");
        switchTab(state.activeTab || "dashboard");
    }

    window.dispatchEvent(new Event("resize"));
}

function switchTab(tabId) {
    state.activeTab = tabId;
    document.querySelectorAll("#sidebarNavSegmentation .nav-item").forEach(item => {
        item.classList.toggle("active", item.getAttribute("data-tab") === tabId);
    });
    document.querySelectorAll(".tab-pane").forEach(pane => {
        pane.classList.toggle("active", pane.id === `tab-${tabId}`);
    });

    // Resize Plotly charts when switching tabs
    window.dispatchEvent(new Event("resize"));
}

// ---------------------------------------------------------------- Clean Data Only Controller
function initCleanOnlyMode() {
    const selectPreviewLimit = document.getElementById("selectRawPreviewLimit");
    selectPreviewLimit?.addEventListener("change", (e) => {
        state.cleanOnly.previewLimit = parseInt(e.target.value);
        loadCleanOnlyPreview(state.cleanOnly.previewLimit);
    });

    const cleanForm = document.getElementById("cleanOnlyRulesForm");
    cleanForm?.addEventListener("submit", async (e) => {
        e.preventDefault();
        await executeCleanOnlyRun();
    });

    const btnRunTop = document.getElementById("btnRunCleanOnlyTop");
    btnRunTop?.addEventListener("click", async () => {
        await executeCleanOnlyRun();
    });

    // Cleaned Table Search & Filtering
    const searchCleanInput = document.getElementById("searchCleanInput");
    const sortCleanBy = document.getElementById("sortCleanBy");
    const sortCleanDir = document.getElementById("sortCleanDir");
    const perPageClean = document.getElementById("perPageClean");
    const btnCleanPrev = document.getElementById("btnCleanPrev");
    const btnCleanNext = document.getElementById("btnCleanNext");

    let cleanSearchTimer = null;
    searchCleanInput?.addEventListener("input", (e) => {
        clearTimeout(cleanSearchTimer);
        cleanSearchTimer = setTimeout(() => {
            state.cleanOnly.search = e.target.value.trim();
            state.cleanOnly.page = 1;
            loadCleanedRows();
        }, 300);
    });

    sortCleanBy?.addEventListener("change", (e) => {
        state.cleanOnly.sortBy = e.target.value;
        loadCleanedRows();
    });

    sortCleanDir?.addEventListener("change", (e) => {
        state.cleanOnly.sortOrder = e.target.value;
        loadCleanedRows();
    });

    perPageClean?.addEventListener("change", (e) => {
        state.cleanOnly.perPage = parseInt(e.target.value);
        state.cleanOnly.page = 1;
        loadCleanedRows();
    });

    btnCleanPrev?.addEventListener("click", () => {
        if (state.cleanOnly.page > 1) {
            state.cleanOnly.page--;
            loadCleanedRows();
        }
    });

    btnCleanNext?.addEventListener("click", () => {
        if (state.cleanOnly.page < state.cleanOnly.totalPages) {
            state.cleanOnly.page++;
            loadCleanedRows();
        }
    });
}

async function loadCleanOnlyPreview(limit = null) {
    const lim = limit || state.cleanOnly.previewLimit || 10;
    try {
        const res = await fetch(`/api/clean-only/preview?limit=${lim}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to load raw preview");

        // Update Anomaly Diagnostics
        document.getElementById("diagTotalRows").textContent = data.total_rows.toLocaleString();
        document.getElementById("diagMissingCust").textContent = data.anomalies.missing_customers.toLocaleString();
        document.getElementById("diagCancellations").textContent = data.anomalies.cancellations.toLocaleString();
        document.getElementById("diagDuplicates").textContent = data.anomalies.duplicates.toLocaleString();
        document.getElementById("diagInvalidQty").textContent = data.anomalies.invalid_quantities.toLocaleString();
        document.getElementById("diagInvalidPrice").textContent = data.anomalies.invalid_prices.toLocaleString();

        // Render Raw Preview Table
        const thead = document.getElementById("theadCleanRawPreview");
        const tbody = document.getElementById("tbodyCleanRawPreview");
        if (thead && tbody && data.preview_rows.length > 0) {
            const cols = Object.keys(data.preview_rows[0]);
            thead.innerHTML = `<tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr>`;
            tbody.innerHTML = data.preview_rows.map(row => `
                <tr>${cols.map(c => `<td>${row[c] !== null ? row[c] : ''}</td>`).join("")}</tr>
            `).join("");
        }
    } catch (err) {
        console.error("Preview error:", err);
    }
}

async function executeCleanOnlyRun() {
    const btnForm = document.getElementById("btnExecuteCleanOnly");
    const btnTop = document.getElementById("btnRunCleanOnlyTop");
    [btnForm, btnTop].forEach(b => {
        if (b) {
            b.disabled = true;
            b.innerHTML = `<span class="spinner"></span> <span>Cleaning Data...</span>`;
        }
    });

    try {
        const payload = {
            max_qty: parseInt(document.getElementById("inputCleanMaxQty")?.value || 300),
            max_price: parseFloat(document.getElementById("inputCleanMaxPrice")?.value || 50),
            remove_cancellations: document.getElementById("checkCleanRemoveCancellations")?.checked ?? true,
            remove_duplicates: document.getElementById("checkCleanRemoveDuplicates")?.checked ?? true
        };

        const res = await fetch("/api/clean-only/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Cleaning run failed");

        state.cleanOnly.report = data.report;

        // Render KPI Cards
        document.getElementById("cleanKpiOriginal").textContent = data.report.original_rows.toLocaleString();
        document.getElementById("cleanKpiCleaned").textContent = data.report.cleaned_rows.toLocaleString();
        document.getElementById("cleanKpiDropped").textContent = data.report.removed_rows.toLocaleString();
        document.getElementById("cleanKpiRetention").textContent = `${data.report.retention_rate}%`;

        // Render Waterfall Table
        const tbodyAudit = document.getElementById("tbodyCleanOnlyAudit");
        if (tbodyAudit && data.report.audit_steps) {
            tbodyAudit.innerHTML = "";
            data.report.audit_steps.forEach(step => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong>${step.step}</strong></td>
                    <td><strong>${step.count.toLocaleString()}</strong></td>
                    <td style="color:${step.dropped > 0 ? 'var(--color-danger)' : 'var(--text-muted)'}">${step.dropped > 0 ? `-${step.dropped.toLocaleString()}` : '0'}</td>
                    <td><span style="font-size:12.5px; color:var(--text-secondary);">${step.reason}</span></td>
                    <td><strong>${step.retention_pct}%</strong></td>
                `;
                tbodyAudit.appendChild(tr);
            });
        }

        // Load actual cleaned rows table
        await loadCleanedRows(1);

        showToast(`Data cleaning complete! Preserved ${data.report.cleaned_rows.toLocaleString()} verified records (${data.report.retention_rate}%).`, "success");

        // Scroll to report section
        document.getElementById("clean-report-section")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (err) {
        showToast(err.message, "error");
    } finally {
        [btnForm, btnTop].forEach(b => {
            if (b) {
                b.disabled = false;
                b.innerHTML = `<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> <span>Clean Dataset Now</span>`;
            }
        });
    }
}

async function loadCleanedRows(pageNum = null) {
    if (pageNum !== null) state.cleanOnly.page = pageNum;

    const tbody = document.getElementById("tbodyCleanedOnly");
    if (!tbody) return;

    try {
        const params = new URLSearchParams({
            page: state.cleanOnly.page,
            per_page: state.cleanOnly.perPage,
            search: state.cleanOnly.search,
            sort_by: state.cleanOnly.sortBy,
            sort_dir: state.cleanOnly.sortOrder
        });

        const res = await fetch(`/api/clean-only/rows?${params.toString()}`);
        const data = await res.json();
        if (!res.ok) {
            if (res.status === 404) {
                // Not cleaned yet, run it automatically
                await executeCleanOnlyRun();
                return;
            }
            throw new Error(data.error || "Failed to load cleaned rows");
        }

        state.cleanOnly.total = data.total;
        state.cleanOnly.totalPages = data.total_pages;

        tbody.innerHTML = "";
        if (data.rows.length === 0) {
            tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4">No matching cleaned transaction records found.</td></tr>`;
        } else {
            data.rows.forEach(row => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong>${row.InvoiceNo || ''}</strong></td>
                    <td>${row.InvoiceDate || ''}</td>
                    <td><span class="badge" style="background:var(--bg-surface-hover); color:var(--text-primary); font-family:var(--font-mono);">#${row.CustomerID || ''}</span></td>
                    <td style="max-width:220px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${row.Description || ''}">${row.Description || ''}</td>
                    <td>${row.Quantity}</td>
                    <td>$${parseFloat(row.UnitPrice).toFixed(2)}</td>
                    <td><strong>$${parseFloat(row.TotalAmount).toFixed(2)}</strong></td>
                    <td>${row.Country || 'United Kingdom'}</td>
                `;
                tbody.appendChild(tr);
            });
        }

        // Pagination Bar
        const start = data.total === 0 ? 0 : (data.page - 1) * data.per_page + 1;
        const end = Math.min(data.page * data.per_page, data.total);
        document.getElementById("cleanPaginationInfo").textContent = `Showing ${start} to ${end} of ${data.total.toLocaleString()} cleaned transactions`;
        document.getElementById("cleanPageDisplay").textContent = `Page ${data.page} of ${data.total_pages}`;
        document.getElementById("btnCleanPrev").disabled = data.page <= 1;
        document.getElementById("btnCleanNext").disabled = data.page >= data.total_pages;
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="8" class="text-center py-4" style="color:var(--color-danger)">${err.message}</td></tr>`;
    }
}

// ---------------------------------------------------------------- Action Buttons
function initActionButtons() {
    const btnLoadSample = document.getElementById("btnLoadSample");
    if (btnLoadSample) {
        btnLoadSample.addEventListener("click", loadSampleDataset);
    }

    const btnQuickRecalculate = document.getElementById("btnQuickRecalculate");
    if (btnQuickRecalculate) {
        btnQuickRecalculate.addEventListener("click", () => executePipelineRun());
    }

    const btnExportSummaryCsv = document.getElementById("btnExportSummaryCsv");
    const btnExportSummaryCsv2 = document.getElementById("btnExportSummaryCsv2");
    [btnExportSummaryCsv, btnExportSummaryCsv2].forEach(btn => {
        if (btn) {
            btn.addEventListener("click", () => {
                window.location.href = "/api/export/summary";
            });
        }
    });
}

// ---------------------------------------------------------------- Initial Pipeline Load
async function loadInitialData() {
    try {
        const statusRes = await fetch("/api/status");
        const status = await statusRes.json();

        updateStatusBadge(status.filename || "online_retail_sample.csv");

        // Execute run to populate results
        await executePipelineRun();
    } catch (err) {
        console.error("Failed to load initial data:", err);
        showToast("Error connecting to analytics service.", "error");
    }
}

async function loadSampleDataset() {
    try {
        showToast("Loading retail sample dataset...", "info");
        const res = await fetch("/api/load-sample", { method: "POST" });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to load sample");

        updateStatusBadge(data.filename);
        showToast("Sample loaded. Executing ML segmentation pipeline...", "info");
        await executePipelineRun();
    } catch (err) {
        showToast(err.message, "error");
    }
}

function updateStatusBadge(filename, count = null) {
    const nameEl = document.getElementById("statusDatasetName");
    const badgeName = document.getElementById("badgeFilename");
    const badgeCount = document.getElementById("badgeCustomerCount");

    if (nameEl) nameEl.textContent = filename;
    if (badgeName) badgeName.textContent = `Dataset: ${filename}`;
    if (count !== null && badgeCount) {
        badgeCount.textContent = `${count.toLocaleString()} customers`;
    }
}

// ---------------------------------------------------------------- Execute Pipeline Run
async function executePipelineRun(customParams = null) {
    try {
        const payload = customParams || {
            k: parseInt(document.getElementById("inputK")?.value || 3),
            max_qty: parseInt(document.getElementById("inputMaxQty")?.value || 300),
            max_price: parseFloat(document.getElementById("inputMaxPrice")?.value || 50),
            remove_cancellations: document.getElementById("checkRemoveCancellations")?.checked ?? true,
            random_state: parseInt(document.getElementById("inputRandomState")?.value || 42)
        };

        const res = await fetch("/api/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Clustering run failed");

        state.pipelineResults = data;

        // Render everything
        renderDashboardKPIs(data.kpis);
        renderSegmentSummaryTable(data.segment_summary);
        renderAllCharts(data);
        renderPlaybook(data.playbook, data.segment_order, data.segment_summary);
        renderDataAudit(data.audit_steps, data.validation);

        // Update badge count
        updateStatusBadge(data.validation?.filename || "online_retail_sample.csv", data.kpis.total_customers);

        // Update customer explorer segment filter options
        updateSegmentFilterOptions(data.segment_order);

        // Fetch customer table records
        loadCustomerPage(1);

        showToast(`Pipeline complete: ${data.kpis.total_customers.toLocaleString()} customers in ${data.kpis.active_k} segments.`, "success");
    } catch (err) {
        console.error("Pipeline run error:", err);
        showToast(err.message, "error");
    }
}

// ---------------------------------------------------------------- Dashboard KPIs & Summary Table
function renderDashboardKPIs(kpis) {
    document.getElementById("kpiTotalCustomers").textContent = kpis.total_customers.toLocaleString();
    document.getElementById("kpiTotalRevenue").textContent = `$${kpis.total_revenue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById("kpiAvgRecency").textContent = `${kpis.avg_recency} days`;
    document.getElementById("kpiAvgSpend").textContent = `$${kpis.avg_spend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById("kpiSilhouette").textContent = kpis.silhouette_score.toFixed(3);
    document.getElementById("kpiSilhouetteLabel").textContent = `Silhouette Score (${kpis.evaluation_verdict})`;
}

function renderSegmentSummaryTable(summary) {
    const tbody = document.getElementById("tbodySegmentSummary");
    if (!tbody) return;

    tbody.innerHTML = "";
    summary.forEach(row => {
        const seg = row.Segment;
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><span class="badge badge-${seg}">${seg}</span></td>
            <td><strong>${row.Customers.toLocaleString()}</strong></td>
            <td>${row["% Customers"]}%</td>
            <td>${row.Avg_Recency} days</td>
            <td>${row.Avg_Frequency} orders</td>
            <td>$${row.Avg_Spend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
            <td><strong>$${row.Total_Spend.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</strong></td>
            <td><span style="font-weight:700; color:${state.colors[seg] || '#2563eb'}">${row["% Revenue"]}%</span></td>
        `;
        tbody.appendChild(tr);
    });
}

// ---------------------------------------------------------------- Chart Renderers (Plotly.js)
function renderAllCharts(data) {
    const baseLayout = getPlotlyThemeLayout();

    // 1. Share of Customer Base Donut Chart
    renderCustomerShareChart(data.segment_summary, baseLayout);

    // 2. Share of Total Revenue Donut Chart
    renderRevenueShareChart(data.segment_summary, baseLayout);

    // 3. 3D RFM Clustering Scatter
    render3DChart(data.scatter_sample, baseLayout);

    // 4. 2D Recency vs Spend with Centroids
    render2DScatter(data.scatter_sample, data.centroids, baseLayout);

    // 5. Boxplots of RFM per segment
    renderBoxplots(data.scatter_sample, data.segment_order, baseLayout);

    // 6. Relative Profile Radar / Grouped Bar
    renderProfileRadar(data.profile_matrix, baseLayout);

    // 7. Elbow Method curve
    renderElbowChart(data.evaluation, baseLayout);

    // 8. Silhouette curve
    renderSilhouetteChart(data.evaluation, baseLayout);
}

function renderCustomerShareChart(summary, baseLayout) {
    const labels = summary.map(s => s.Segment);
    const values = summary.map(s => s.Customers);
    const colors = labels.map(l => state.colors[l] || "#94a3b8");

    const plotData = [{
        type: "pie",
        labels: labels,
        values: values,
        hole: 0.55,
        textinfo: "label+percent",
        hoverinfo: "label+value+percent",
        marker: { colors: colors },
        textposition: "outside",
        automargin: true
    }];

    const layout = {
        ...baseLayout,
        showlegend: false,
        margin: { t: 20, r: 20, l: 20, b: 20 }
    };

    Plotly.react("chartCustomerShare", plotData, layout, { responsive: true, displayModeBar: false });
}

function renderRevenueShareChart(summary, baseLayout) {
    const labels = summary.map(s => s.Segment);
    const values = summary.map(s => s.Total_Spend);
    const colors = labels.map(l => state.colors[l] || "#94a3b8");

    const plotData = [{
        type: "pie",
        labels: labels,
        values: values,
        hole: 0.55,
        textinfo: "label+percent",
        hoverinfo: "label+value+percent",
        marker: { colors: colors },
        textposition: "outside",
        automargin: true
    }];

    const layout = {
        ...baseLayout,
        showlegend: false,
        margin: { t: 20, r: 20, l: 20, b: 20 }
    };

    Plotly.react("chartRevenueShare", plotData, layout, { responsive: true, displayModeBar: false });
}

function render3DChart(sample, baseLayout) {
    const isDark = state.theme === "dark";
    const segments = [...new Set(sample.map(d => d.segment))];
    const traces = segments.map(seg => {
        const pts = sample.filter(d => d.segment === seg);
        return {
            x: pts.map(p => p.r),
            y: pts.map(p => p.log_f),
            z: pts.map(p => p.log_m),
            text: pts.map(p => `Customer: ${p.id}<br>Recency: ${p.r}d<br>Frequency: ${p.f} orders<br>Spend: $${p.m.toFixed(2)}`),
            hoverinfo: "text",
            mode: "markers",
            name: seg,
            marker: {
                size: 3.5,
                color: state.colors[seg] || "#3b82f6",
                opacity: 0.75
            },
            type: "scatter3d"
        };
    });

    const layout = {
        ...baseLayout,
        scene: {
            xaxis: { title: "Recency (Days)", gridcolor: isDark ? "#1f2937" : "#e2e8f0" },
            yaxis: { title: "log10(Frequency)", gridcolor: isDark ? "#1f2937" : "#e2e8f0" },
            zaxis: { title: "log10(Monetary)", gridcolor: isDark ? "#1f2937" : "#e2e8f0" },
            bgcolor: isDark ? "#111827" : "#ffffff"
        },
        margin: { t: 0, r: 0, l: 0, b: 0 },
        legend: { x: 0, y: 1 }
    };

    Plotly.react("chart3DView", traces, layout, { responsive: true, displaylogo: false });
}

function render2DScatter(sample, centroids, baseLayout) {
    const isDark = state.theme === "dark";
    const segments = [...new Set(sample.map(d => d.segment))];
    const traces = segments.map(seg => {
        const pts = sample.filter(d => d.segment === seg);
        return {
            x: pts.map(p => p.r),
            y: pts.map(p => p.m),
            text: pts.map(p => `Customer ${p.id}<br>Recency: ${p.r}d<br>Spend: $${p.m.toFixed(2)}`),
            hoverinfo: "text",
            mode: "markers",
            name: seg,
            marker: {
                size: 5,
                color: state.colors[seg] || "#3b82f6",
                opacity: 0.6
            },
            type: "scatter"
        };
    });

    // Add Centroid trace
    if (centroids && centroids.length > 0) {
        traces.push({
            x: centroids.map(c => c.Recency),
            y: centroids.map(c => c.Monetary),
            text: centroids.map(c => `Centroid: ${c.Segment}<br>Avg Recency: ${c.Recency}d<br>Avg Spend: $${c.Monetary}`),
            hoverinfo: "text",
            mode: "markers+text",
            name: "Centroids",
            marker: {
                size: 16,
                symbol: "star",
                color: "#eab308",
                line: { color: "#000000", width: 1.5 }
            },
            type: "scatter"
        });
    }

    const layout = {
        ...baseLayout,
        xaxis: {
            title: "Recency (Days since last purchase)",
            gridcolor: isDark ? "#1f2937" : "#f1f5f9"
        },
        yaxis: {
            title: "Total Spend (Log Scale)",
            type: "log",
            gridcolor: isDark ? "#1f2937" : "#f1f5f9"
        },
        legend: { orientation: "h", y: -0.2 }
    };

    Plotly.react("chart2DScatter", traces, layout, { responsive: true, displaylogo: false });
}

function renderBoxplots(sample, order, baseLayout) {
    const isDark = state.theme === "dark";
    const traces = [];

    order.forEach(seg => {
        const pts = sample.filter(d => d.segment === seg);
        traces.push({
            y: pts.map(p => p.m),
            name: seg,
            type: "box",
            marker: { color: state.colors[seg] || "#3b82f6" },
            boxpoints: false
        });
    });

    const layout = {
        ...baseLayout,
        yaxis: {
            title: "Monetary Spend (Log Scale)",
            type: "log",
            gridcolor: isDark ? "#1f2937" : "#f1f5f9"
        },
        showlegend: false
    };

    Plotly.react("chartBoxplots", traces, layout, { responsive: true, displaylogo: false });
}

function renderProfileRadar(matrix, baseLayout) {
    const isDark = state.theme === "dark";
    const segments = matrix.map(m => m.segment);

    const traceRecency = {
        x: segments,
        y: matrix.map(m => m.recency_z),
        name: "Recency (z-score)",
        type: "bar",
        marker: { color: "#6366f1" }
    };

    const traceFreq = {
        x: segments,
        y: matrix.map(m => m.frequency_z),
        name: "Frequency (z-score)",
        type: "bar",
        marker: { color: "#3b82f6" }
    };

    const traceSpend = {
        x: segments,
        y: matrix.map(m => m.monetary_z),
        name: "Monetary (z-score)",
        type: "bar",
        marker: { color: "#10b981" }
    };

    const layout = {
        ...baseLayout,
        barmode: "group",
        yaxis: {
            title: "Standardized Relative Level (Z-score)",
            gridcolor: isDark ? "#1f2937" : "#f1f5f9"
        },
        legend: { orientation: "h", y: -0.2 }
    };

    Plotly.react("chartRadarProfile", [traceRecency, traceFreq, traceSpend], layout, { responsive: true, displaylogo: false });
}

function renderElbowChart(evaluation, baseLayout) {
    const isDark = state.theme === "dark";
    const trace = {
        x: evaluation.ks,
        y: evaluation.wcss,
        mode: "lines+markers",
        name: "WCSS (Inertia)",
        line: { color: "#f59e0b", width: 2.5 },
        marker: { size: 7, color: "#d97706" }
    };

    const layout = {
        ...baseLayout,
        xaxis: { title: "Number of Clusters (k)", dtick: 1, gridcolor: isDark ? "#1f2937" : "#f1f5f9" },
        yaxis: { title: "Within-Cluster Sum of Squares (WCSS)", gridcolor: isDark ? "#1f2937" : "#f1f5f9" },
        shapes: [{
            type: "line",
            x0: evaluation.chosen_k,
            x1: evaluation.chosen_k,
            y0: 0,
            y1: 1,
            yref: "paper",
            line: { color: "#94a3b8", width: 1.5, dash: "dot" }
        }]
    };

    Plotly.react("chartElbow", [trace], layout, { responsive: true, displaylogo: false });
}

function renderSilhouetteChart(evaluation, baseLayout) {
    const isDark = state.theme === "dark";
    const trace = {
        x: evaluation.ks,
        y: evaluation.silhouette_scores,
        mode: "lines+markers",
        name: "Silhouette Score",
        line: { color: "#2563eb", width: 2.5 },
        marker: { size: 7, color: "#1d4ed8" }
    };

    const layout = {
        ...baseLayout,
        xaxis: { title: "Number of Clusters (k)", dtick: 1, gridcolor: isDark ? "#1f2937" : "#f1f5f9" },
        yaxis: { title: "Mean Silhouette Coefficient", gridcolor: isDark ? "#1f2937" : "#f1f5f9" },
        shapes: [{
            type: "line",
            x0: evaluation.chosen_k,
            x1: evaluation.chosen_k,
            y0: 0,
            y1: 1,
            yref: "paper",
            line: { color: "#94a3b8", width: 1.5, dash: "dot" }
        }]
    };

    Plotly.react("chartSilhouette", [trace], layout, { responsive: true, displaylogo: false });
}

// ---------------------------------------------------------------- Playbook Renderer
function renderPlaybook(playbook, order, summary) {
    const grid = document.getElementById("playbookGrid");
    if (!grid) return;

    grid.innerHTML = "";
    order.forEach(seg => {
        const info = playbook[seg] || {
            title: `Segment: ${seg}`,
            persona: "Customer group derived from RFM clustering.",
            strategies: ["Engage customers using personalized communications."]
        };

        const sumData = summary.find(s => s.Segment === seg) || {};
        const stratItems = info.strategies.map(s => `<li>${s}</li>`).join("");

        const card = document.createElement("div");
        card.className = "playbook-card";
        card.innerHTML = `
            <div class="playbook-header">
                <span class="playbook-title">${info.title}</span>
                <span class="badge badge-${seg}">${seg}</span>
            </div>
            <div style="font-size:12.5px; color:var(--text-secondary); margin-bottom:12px;">
                <strong>${(sumData.Customers || 0).toLocaleString()}</strong> customers (${sumData["% Customers"] || 0}%) producing 
                <strong>$${(sumData.Total_Spend || 0).toLocaleString(undefined, {minimumFractionDigits: 2})}</strong> (${sumData["% Revenue"] || 0}% revenue)
            </div>
            <p class="playbook-persona">${info.persona}</p>
            <div class="playbook-strategies">
                <h4>Recommended Growth & Retention Playbook:</h4>
                <ul>${stratItems}</ul>
            </div>
        `;
        grid.appendChild(card);
    });
}

// ---------------------------------------------------------------- Data Audit & Validation Renderer
function renderDataAudit(steps, validation) {
    const tbodyAudit = document.getElementById("tbodyCleaningAudit");
    if (tbodyAudit && steps) {
        tbodyAudit.innerHTML = "";
        const initialCount = steps[0]?.count || 1;
        steps.forEach(s => {
            const tr = document.createElement("tr");
            const retentionPct = ((s.count / initialCount) * 100).toFixed(1);
            tr.innerHTML = `
                <td><strong>${s.step}</strong></td>
                <td>${s.count.toLocaleString()}</td>
                <td style="color:${s.dropped > 0 ? 'var(--color-danger)' : 'var(--text-muted)'}">${s.dropped > 0 ? `-${s.dropped.toLocaleString()}` : '0'}</td>
                <td><span style="font-weight:600;">${retentionPct}%</span></td>
            `;
            tbodyAudit.appendChild(tr);
        });
    }

    // Raw preview table
    if (validation?.sample_preview) {
        const thead = document.getElementById("theadRawPreview");
        const tbody = document.getElementById("tbodyRawPreview");
        if (thead && tbody) {
            const preview = validation.sample_preview;
            if (preview.length > 0) {
                const cols = Object.keys(preview[0]);
                thead.innerHTML = `<tr>${cols.map(c => `<th>${c}</th>`).join("")}</tr>`;
                tbody.innerHTML = preview.map(row => `
                    <tr>${cols.map(c => `<td>${row[c] !== null ? row[c] : ''}</td>`).join("")}</tr>
                `).join("");
            }
        }
    }
}

// ---------------------------------------------------------------- Customer Explorer Controller
function initCustomerExplorer() {
    const searchInput = document.getElementById("custSearchInput");
    const segFilter = document.getElementById("custSegmentFilter");
    const sortBy = document.getElementById("custSortBy");
    const sortDir = document.getElementById("custSortDir");
    const perPage = document.getElementById("custPerPage");
    const btnPrev = document.getElementById("btnPrevPage");
    const btnNext = document.getElementById("btnNextPage");

    let debounceTimer = null;
    searchInput?.addEventListener("input", (e) => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            state.customers.search = e.target.value.trim();
            state.customers.page = 1;
            loadCustomerPage();
        }, 300);
    });

    segFilter?.addEventListener("change", (e) => {
        state.customers.segment = e.target.value;
        state.customers.page = 1;
        loadCustomerPage();
    });

    sortBy?.addEventListener("change", (e) => {
        state.customers.sortBy = e.target.value;
        loadCustomerPage();
    });

    sortDir?.addEventListener("change", (e) => {
        state.customers.sortOrder = e.target.value;
        loadCustomerPage();
    });

    perPage?.addEventListener("change", (e) => {
        state.customers.perPage = parseInt(e.target.value);
        state.customers.page = 1;
        loadCustomerPage();
    });

    btnPrev?.addEventListener("click", () => {
        if (state.customers.page > 1) {
            state.customers.page--;
            loadCustomerPage();
        }
    });

    btnNext?.addEventListener("click", () => {
        if (state.customers.page < state.customers.totalPages) {
            state.customers.page++;
            loadCustomerPage();
        }
    });

    // Close detail modal
    document.getElementById("btnCloseCustDetailModal")?.addEventListener("click", closeCustomerDetailModal);
    document.getElementById("btnCloseCustDetailBtn")?.addEventListener("click", closeCustomerDetailModal);
}

function updateSegmentFilterOptions(order) {
    const segFilter = document.getElementById("custSegmentFilter");
    if (!segFilter) return;

    segFilter.innerHTML = '<option value="all">All Segments</option>';
    order.forEach(seg => {
        const opt = document.createElement("option");
        opt.value = seg;
        opt.textContent = seg;
        segFilter.appendChild(opt);
    });
}

async function loadCustomerPage(pageNum = null) {
    if (pageNum !== null) state.customers.page = pageNum;

    const tbody = document.getElementById("tbodyCustomers");
    if (!tbody) return;

    try {
        const params = new URLSearchParams({
            page: state.customers.page,
            per_page: state.customers.perPage,
            search: state.customers.search,
            segment: state.customers.segment,
            sort_by: state.customers.sortBy,
            sort_order: state.customers.sortOrder
        });

        const res = await fetch(`/api/customers?${params.toString()}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Failed to load customers");

        state.customers.total = data.total;
        state.customers.totalPages = data.total_pages;

        // Render rows
        tbody.innerHTML = "";
        if (data.customers.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4">No matching customer records found.</td></tr>`;
        } else {
            data.customers.forEach(cust => {
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td><strong>#${cust.CustomerID}</strong></td>
                    <td><span class="badge badge-${cust.Segment}">${cust.Segment}</span></td>
                    <td>${cust.Recency} days</td>
                    <td>${cust.Frequency} orders</td>
                    <td>$${cust.Monetary.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                    <td>Cluster ${cust.Cluster}</td>
                    <td>
                        <button class="btn btn-outline btn-sm" onclick="openCustomerDetail('${cust.CustomerID}')">
                            <span>Inspect</span>
                        </button>
                    </td>
                `;
                tbody.appendChild(tr);
            });
        }

        // Update pagination bar
        const start = data.total === 0 ? 0 : (data.page - 1) * data.per_page + 1;
        const end = Math.min(data.page * data.per_page, data.total);
        document.getElementById("custPaginationInfo").textContent = `Showing ${start} to ${end} of ${data.total.toLocaleString()} customers`;
        document.getElementById("pageNumberDisplay").textContent = `Page ${data.page} of ${data.total_pages}`;
        document.getElementById("btnPrevPage").disabled = data.page <= 1;
        document.getElementById("btnNextPage").disabled = data.page >= data.total_pages;
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="7" class="text-center py-4" style="color:var(--color-danger)">${err.message}</td></tr>`;
    }
}

// ---------------------------------------------------------------- Customer Details Modal
window.openCustomerDetail = async function(customerId) {
    const modal = document.getElementById("customerDetailModal");
    const body = document.getElementById("custDetailBody");
    const title = document.getElementById("custDetailTitle");
    const subtitle = document.getElementById("custDetailSubtitle");

    title.textContent = `Customer Profile: #${customerId}`;
    subtitle.textContent = "Loading analytics...";
    body.innerHTML = `<div class="text-center py-4"><span class="spinner" style="border-top-color:var(--primary); width:28px; height:28px;"></span></div>`;
    modal.style.display = "flex";

    try {
        const res = await fetch(`/api/customer/${customerId}`);
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Customer not found");

        subtitle.textContent = `Cluster ${data.cluster} &bull; ${data.segment} Tier`;

        body.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <div>
                    <span class="badge badge-${data.segment}" style="font-size:14px; padding:4px 12px;">${data.segment}</span>
                </div>
                <div style="font-size:13px; color:var(--text-secondary);">
                    Customer ID: <strong>#${data.customer_id}</strong>
                </div>
            </div>

            <!-- Percentile Comparisons -->
            <div class="percentile-grid">
                <div class="percentile-card">
                    <div class="percentile-label">Recency Freshness</div>
                    <div class="percentile-num">${data.percentiles.recency_percentile}%</div>
                    <div class="progress-track">
                        <div class="progress-fill" style="width:${data.percentiles.recency_percentile}%; background-color:var(--color-vip);"></div>
                    </div>
                    <small style="color:var(--text-muted); font-size:11px; margin-top:4px; display:block;">${data.recency} days ago</small>
                </div>

                <div class="percentile-card">
                    <div class="percentile-label">Order Frequency</div>
                    <div class="percentile-num">${data.percentiles.frequency_percentile}%</div>
                    <div class="progress-track">
                        <div class="progress-fill" style="width:${data.percentiles.frequency_percentile}%; background-color:var(--color-regular);"></div>
                    </div>
                    <small style="color:var(--text-muted); font-size:11px; margin-top:4px; display:block;">${data.frequency} lifetime orders</small>
                </div>

                <div class="percentile-card">
                    <div class="percentile-label">Spend Volume</div>
                    <div class="percentile-num">${data.percentiles.monetary_percentile}%</div>
                    <div class="progress-track">
                        <div class="progress-fill" style="width:${data.percentiles.monetary_percentile}%; background-color:var(--color-rare);"></div>
                    </div>
                    <small style="color:var(--text-muted); font-size:11px; margin-top:4px; display:block;">$${data.monetary.toLocaleString(undefined, {minimumFractionDigits: 2})}</small>
                </div>
            </div>

            <div style="margin-top:20px; padding:16px; background-color:var(--bg-surface-hover); border-radius:var(--radius-md);">
                <h4 style="font-size:14px; font-weight:700; margin-bottom:8px; color:var(--text-primary);">${data.segment_info.title}</h4>
                <p style="font-size:13px; color:var(--text-secondary); margin-bottom:12px;">${data.segment_info.persona}</p>
                <div style="font-size:12px; font-weight:600; text-transform:uppercase; color:var(--text-muted); margin-bottom:6px;">Recommended Strategy:</div>
                <ul style="padding-left:18px; font-size:12.5px; color:var(--text-primary); display:flex; flex-direction:column; gap:6px;">
                    ${data.segment_info.strategies.map(s => `<li>${s}</li>`).join("")}
                </ul>
            </div>
        `;
    } catch (err) {
        body.innerHTML = `<div style="color:var(--color-danger); text-align:center; padding:20px;">${err.message}</div>`;
    }
};

function closeCustomerDetailModal() {
    document.getElementById("customerDetailModal").style.display = "none";
}

// ---------------------------------------------------------------- Tuning Form Controller
function initTuningForm() {
    const inputK = document.getElementById("inputK");
    const valK = document.getElementById("valK");
    if (inputK && valK) {
        inputK.addEventListener("input", () => {
            valK.textContent = inputK.value;
        });
    }

    const form = document.getElementById("tuningForm");
    if (form) {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();
            const btn = document.getElementById("btnRunTuning");
            btn.disabled = true;
            btn.innerHTML = `<span class="spinner"></span> <span>Running ML Pipeline...</span>`;

            try {
                const params = {
                    k: parseInt(document.getElementById("inputK").value),
                    max_qty: parseInt(document.getElementById("inputMaxQty").value),
                    max_price: parseFloat(document.getElementById("inputMaxPrice").value),
                    remove_cancellations: document.getElementById("checkRemoveCancellations").checked,
                    random_state: parseInt(document.getElementById("inputRandomState").value)
                };
                await executePipelineRun(params);
            } finally {
                btn.disabled = false;
                btn.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                    <span>Run Pipeline & Update Models</span>
                `;
            }
        });
    }
}

// ---------------------------------------------------------------- File Upload Modal Controller
function initUploadModal() {
    const modal = document.getElementById("uploadModal");
    const openBtn = document.getElementById("btnOpenUploadModal");
    const closeBtn = document.getElementById("btnCloseUploadModal");
    const cancelBtn = document.getElementById("btnCancelUpload");
    const dropZone = document.getElementById("dropZone");
    const fileInput = document.getElementById("fileInput");
    const fileInfo = document.getElementById("uploadFileInfo");
    const fileName = document.getElementById("selectedFileName");
    const fileSize = document.getElementById("selectedFileSize");
    const submitBtn = document.getElementById("btnSubmitUpload");
    const validationBox = document.getElementById("uploadValidationBox");

    let selectedFile = null;

    function openModal() {
        modal.style.display = "flex";
        resetUploadState();
    }

    function closeModal() {
        modal.style.display = "none";
        resetUploadState();
    }

    function resetUploadState() {
        selectedFile = null;
        fileInput.value = "";
        fileInfo.style.display = "none";
        validationBox.style.display = "none";
        submitBtn.disabled = true;
    }

    openBtn?.addEventListener("click", openModal);
    closeBtn?.addEventListener("click", closeModal);
    cancelBtn?.addEventListener("click", closeModal);

    // Dropzone interactions
    dropZone?.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone?.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone?.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            handleFileSelection(e.dataTransfer.files[0]);
        }
    });

    fileInput?.addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            handleFileSelection(e.target.files[0]);
        }
    });

    function handleFileSelection(file) {
        selectedFile = file;
        fileName.textContent = file.name;
        fileSize.textContent = `${(file.size / (1024 * 1024)).toFixed(2)} MB`;
        fileInfo.style.display = "flex";
        validationBox.style.display = "none";
        submitBtn.disabled = false;
    }

    submitBtn?.addEventListener("click", async () => {
        if (!selectedFile) return;

        submitBtn.disabled = true;
        document.getElementById("uploadBtnText").textContent = "Uploading...";
        document.getElementById("uploadSpinner").style.display = "inline-block";

        const formData = new FormData();
        formData.append("file", selectedFile);

        try {
            const res = await fetch("/api/upload", {
                method: "POST",
                body: formData
            });

            const data = await res.json();
            if (!res.ok) throw new Error(data.error || "Upload failed");

            // Show validation check
            validationBox.style.display = "block";
            if (data.validation.is_valid) {
                validationBox.className = "validation-box validation-success";
                validationBox.innerHTML = `
                    <strong>File Validated!</strong> Detected ${data.validation.total_rows.toLocaleString()} rows. Required columns verified.
                `;
                showToast(`File "${data.filename}" uploaded successfully.`, "success");

                // Auto-run according to active mode after 1s
                setTimeout(async () => {
                    closeModal();
                    if (state.mode === "clean-only") {
                        await loadCleanOnlyPreview();
                        await executeCleanOnlyRun();
                    } else {
                        await executePipelineRun();
                    }
                }, 1000);
            } else {
                validationBox.className = "validation-box validation-error";
                validationBox.innerHTML = `
                    <strong>Validation Failed:</strong> Missing required columns: ${data.validation.missing_columns.join(", ")}
                `;
            }
        } catch (err) {
            validationBox.style.display = "block";
            validationBox.className = "validation-box validation-error";
            const msg = (err.name === "TypeError" && err.message.toLowerCase().includes("fetch"))
                ? "Server is offline or unreachable. Please run 'python run.py' in your terminal."
                : (err.message || "Upload failed");
            validationBox.textContent = msg;
            showToast(msg, "error");
        } finally {
            submitBtn.disabled = false;
            document.getElementById("uploadBtnText").textContent = "Upload & Process";
            document.getElementById("uploadSpinner").style.display = "none";
        }
    });
}

// ---------------------------------------------------------------- Toast Notifications
function showToast(message, type = "info") {
    const container = document.getElementById("toastContainer");
    if (!container) return;

    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <span>${message}</span>
        <button style="background:transparent; border:none; color:inherit; cursor:pointer; margin-left:12px; font-size:16px;">&times;</button>
    `;

    toast.querySelector("button").addEventListener("click", () => toast.remove());

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = "0";
        setTimeout(() => toast.remove(), 250);
    }, 4500);
}
