// Apply saved theme immediately to prevent flash
(function() {
    if (localStorage.getItem('dashboard-theme') === 'dark') {
        document.body.classList.add('dark-theme');
    }
})();

// Create toggle button and bind events after Dash renders
(function() {
    function init() {
        if (document.getElementById('theme-toggle')) return;

        var btn = document.createElement('button');
        btn.id = 'theme-toggle';
        btn.setAttribute('aria-label', 'Toggle theme');
        btn.title = 'Switch design';

        // Sun icon (shown in light mode → click to go dark)
        btn.innerHTML =
            '<svg class="icon-light" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">' +
                '<circle cx="12" cy="12" r="5"/>' +
                '<line x1="12" y1="1" x2="12" y2="3"/>' +
                '<line x1="12" y1="21" x2="12" y2="23"/>' +
                '<line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>' +
                '<line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>' +
                '<line x1="1" y1="12" x2="3" y2="12"/>' +
                '<line x1="21" y1="12" x2="23" y2="12"/>' +
                '<line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>' +
                '<line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>' +
            '</svg>' +
            '<svg class="icon-dark" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">' +
                '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>' +
            '</svg>';

        btn.addEventListener('click', function() {
            document.body.classList.toggle('dark-theme');
            var isDark = document.body.classList.contains('dark-theme');
            localStorage.setItem('dashboard-theme', isDark ? 'dark' : 'light');
            updatePlotlyTheme(isDark);
        });

        document.body.appendChild(btn);

        // If dark theme was applied on load, update charts once they render
        if (document.body.classList.contains('dark-theme')) {
            waitForCharts(function() { updatePlotlyTheme(true); });
        }
    }

    function waitForCharts(cb) {
        var attempts = 0;
        var interval = setInterval(function() {
            attempts++;
            if (document.querySelector('.js-plotly-plot') || attempts > 20) {
                clearInterval(interval);
                setTimeout(cb, 300);
            }
        }, 200);
    }

    // Poll for Dash to finish rendering
    if (document.readyState === 'complete') {
        init();
    } else {
        window.addEventListener('load', init);
    }
    // Also try after a delay in case Dash renders late
    setTimeout(init, 1000);
})();

function updatePlotlyTheme(isDark) {
    var themes = {
        dark: {
            paper: '#0f172a', plot: '#1e293b',
            fontColor: '#94a3b8', grid: '#334155',
            heading: '#f1f5f9',
            legendBg: 'rgba(30,41,59,0.9)',
            legendFont: '#e2e8f0', legendBorder: '#475569',
        },
        light: {
            paper: '#ffffff', plot: '#f8f9fa',
            fontColor: '#6c757d', grid: '#e0e0e0',
            heading: '#1a1a2e',
            legendBg: 'rgba(248,249,250,0.9)',
            legendFont: '#333333', legendBorder: '#e0e0e0',
        },
    };

    var t = isDark ? themes.dark : themes.light;

    document.querySelectorAll('.js-plotly-plot').forEach(function(plot) {
        var fl = plot._fullLayout;
        if (!fl) return;

        var update = {
            paper_bgcolor: t.paper,
            plot_bgcolor: t.plot,
            'font.color': t.fontColor,
            'font.family': 'Inter',
        };

        Object.keys(fl).forEach(function(k) {
            if (/^[xy]axis\d*$/.test(k)) {
                update[k + '.gridcolor'] = t.grid;
                update[k + '.zerolinecolor'] = t.grid;
            }
        });

        if (fl.annotations && fl.annotations.length) {
            update.annotations = fl.annotations.map(function(ann) {
                var copy = Object.assign({}, ann);
                copy.font = Object.assign({}, ann.font || {}, { color: t.heading });
                return copy;
            });
        }

        if (fl.legend) {
            update['legend.font.color'] = t.legendFont;
            update['legend.bgcolor'] = t.legendBg;
            update['legend.bordercolor'] = t.legendBorder;
        }

        Plotly.relayout(plot, update);
    });
}
