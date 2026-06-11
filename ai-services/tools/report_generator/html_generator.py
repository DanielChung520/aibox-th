import json
from datetime import datetime


RECHART_CDN = (
    '<script src="https://cdn.jsdelivr.net/npm/react@18.2.0/umd/react.production.min.js"></script>\n'
    '<script src="https://cdn.jsdelivr.net/npm/react-dom@18.2.0/umd/react-dom.production.min.js"></script>\n'
    '<script src="https://cdn.jsdelivr.net/npm/prop-types@15.8.1/prop-types.min.js"></script>\n'
    '<script src="https://cdn.jsdelivr.net/npm/recharts@2.15.0/umd/Recharts.min.js"></script>'
)

COLORS = '["#0088FE","#00C49F","#FFBB28","#FF8042","#8884D8","#82CA9D","#FFC658","#8DD1E1","#A4DE6C","#D0ED57"]'

CHART_HTML_MAP = {
    "pie": """
        <div id="chart-container"></div>
        <script>
          var data = __DATA__;
          var colors = __COLORS__;
          var container = document.getElementById('chart-container');
          function renderChart() {
            var width = container.clientWidth || 800;
            ReactDOM.render(
              React.createElement(Recharts.PieChart, {width: width, height: width * 0.5},
                React.createElement(Recharts.Pie, {
                  data: data, cx: '50%', cy: '50%', innerRadius: width * 0.12, outerRadius: width * 0.22,
                  labelLine: false,
                  label: function(entry) { return entry.name + ': ' + (entry.percent * 100).toFixed(1) + '%'; },
                  dataKey: 'value'
                },
                  data.map(function(entry, index) { return React.createElement(Recharts.Cell, {key: index, fill: colors[index % colors.length]}); })
                ),
                React.createElement(Recharts.Tooltip, null),
                __LEGEND__
              ),
              container
            );
          }
          renderChart();
          window.addEventListener('resize', renderChart);
        </script>""",
    "bar": """
        <div id="chart-container"></div>
        <script>
          var data = __DATA__;
          var container = document.getElementById('chart-container');
          function renderChart() {
            var width = container.clientWidth || 800;
            ReactDOM.render(
              React.createElement(Recharts.BarChart, {width: width, height: width * 0.5, data: data},
                React.createElement(Recharts.XAxis, {dataKey: 'name', interval: 0, angle: -30, textAnchor: 'end', height: 80}),
                React.createElement(Recharts.YAxis, null),
                React.createElement(Recharts.Tooltip, null),
                __LEGEND__,
                React.createElement(Recharts.Bar, {dataKey: 'value', fill: '#8884d8'})
              ),
              container
            );
          }
          renderChart();
          window.addEventListener('resize', renderChart);
        </script>""",
    "line": """
        <div id="chart-container"></div>
        <script>
          var data = __DATA__;
          var container = document.getElementById('chart-container');
          function renderChart() {
            var width = container.clientWidth || 800;
            ReactDOM.render(
              React.createElement(Recharts.LineChart, {width: width, height: width * 0.5, data: data},
                React.createElement(Recharts.XAxis, {dataKey: 'name'}),
                React.createElement(Recharts.YAxis, null),
                React.createElement(Recharts.Tooltip, null),
                __LEGEND__,
                React.createElement(Recharts.Line, {type: 'monotone', dataKey: 'value', stroke: '#8884d8', strokeWidth: 2})
              ),
              container
            );
          }
          renderChart();
          window.addEventListener('resize', renderChart);
        </script>""",
    "area": """
        <div id="chart-container"></div>
        <script>
          var data = __DATA__;
          var container = document.getElementById('chart-container');
          function renderChart() {
            var width = container.clientWidth || 800;
            ReactDOM.render(
              React.createElement(Recharts.AreaChart, {width: width, height: width * 0.5, data: data},
                React.createElement(Recharts.XAxis, {dataKey: 'name'}),
                React.createElement(Recharts.YAxis, null),
                React.createElement(Recharts.Tooltip, null),
                __LEGEND__,
                React.createElement(Recharts.Area, {type: 'monotone', dataKey: 'value', stroke: '#8884d8', fill: '#8884d8', fillOpacity: 0.3})
              ),
              container
            );
          }
          renderChart();
          window.addEventListener('resize', renderChart);
        </script>""",
    "scatter": """
        <div id="chart-container"></div>
        <script>
          var data = __DATA__;
          var container = document.getElementById('chart-container');
          function renderChart() {
            var width = container.clientWidth || 800;
            ReactDOM.render(
              React.createElement(Recharts.ScatterChart, {width: width, height: width * 0.5, data: data},
                React.createElement(Recharts.XAxis, {dataKey: 'name', name: 'x'}),
                React.createElement(Recharts.YAxis, {dataKey: 'value', name: 'y'}),
                React.createElement(Recharts.Tooltip, {cursor: {strokeDasharray: '3 3'}}),
                React.createElement(Recharts.Scatter, {data: data, fill: '#8884d8'})
              ),
              container
            );
          }
          renderChart();
          window.addEventListener('resize', renderChart);
        </script>""",
    "combo": """
        <div id="chart-container"></div>
        <script>
          var data = __DATA__;
          var container = document.getElementById('chart-container');
          function renderChart() {
            var width = container.clientWidth || 800;
            ReactDOM.render(
              React.createElement(Recharts.ComposedChart, {width: width, height: width * 0.5, data: data},
                React.createElement(Recharts.XAxis, {dataKey: 'name'}),
                React.createElement(Recharts.YAxis, null),
                React.createElement(Recharts.Tooltip, null),
                __LEGEND__,
                React.createElement(Recharts.Bar, {dataKey: 'value', fill: '#8884d8'}),
                React.createElement(Recharts.Line, {type: 'monotone', dataKey: 'value', stroke: '#FF8042', strokeWidth: 2})
              ),
              container
            );
          }
          renderChart();
          window.addEventListener('resize', renderChart);
        </script>""",
}

HINTS_TEMPLATE = """
        <section class="hints-section">
            <h2 class="hints-title">💡 備註</h2>
            <div class="hints-content">
                <p>{hints}</p>
            </div>
        </section>
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {rechart_cdn}
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .header h1 {{
            font-size: 2rem;
            margin-bottom: 8px;
        }}
        .header .meta {{
            opacity: 0.9;
            font-size: 0.9rem;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 24px;
        }}
        .chart-section {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 24px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .chart-title {{
            font-size: 1.2rem;
            font-weight: 600;
            color: #333;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid #667eea;
        }}
        .chart-container {{
            display: flex;
            justify-content: center;
            align-items: center;
            width: 100%;
            min-height: 400px;
            padding: 16px 0;
            box-sizing: border-box;
        }}
        .analysis-section {{
            background: white;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }}
        .analysis-title {{
            font-size: 1.2rem;
            font-weight: 600;
            color: #333;
            margin-bottom: 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid #00C49F;
        }}
        .analysis-content {{
            color: #555;
            line-height: 1.8;
        }}
        .hints-section {{
            background: #fffb ea;
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            border-left: 4px solid #FFBB28;
        }}
        .hints-title {{
            font-size: 1.2rem;
            font-weight: 600;
            color: #333;
            margin-bottom: 16px;
        }}
        .hints-content {{
            color: #666;
            line-height: 1.8;
        }}
        .footer {{
            text-align: center;
            padding: 24px;
            color: #888;
            font-size: 0.85rem;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 12px;
            background: #667eea;
            color: white;
            border-radius: 20px;
            font-size: 0.8rem;
            margin-right: 8px;
        }}
    </style>
</head>
<body>
    <header class="header">
        <h1>{title}</h1>
        <div class="meta">
            <span class="badge">{chart_type}</span>
            製作日期：{timestamp} | 作者：{author}
        </div>
    </header>

    <main class="container">
        <section class="chart-section">
            <h2 class="chart-title">📊 資料視覺化</h2>
            <div class="chart-container">
                {chart_html}
            </div>
        </section>

        <section class="analysis-section">
            <h2 class="analysis-title">📝 資料分析報告</h2>
            <div class="analysis-content">
                {analysis_summary}
            </div>
        </section>

        {hints_block}
    </main>

    <footer class="footer">
        <p>此報告由 tool_reports 自動生成 | 資料僅在本地處理，不上傳外部服務</p>
    </footer>
</body>
</html>"""


def _build_legend_js(show: bool, position: str) -> str:
    if not show:
        return ""
    pos_map = {
        "top":    '{verticalAlign: "top",    align: "center"}',
        "bottom": '{verticalAlign: "bottom", align: "center"}',
        "left":   '{verticalAlign: "middle", align: "left",   layout: "vertical"}',
        "right":  '{verticalAlign: "middle", align: "right",  layout: "vertical"}',
    }
    props = pos_map.get(position, pos_map["bottom"])
    return f"React.createElement(Recharts.Legend, {props})"


def build_chart_html(chart_data: list, chart_type: str, legend_show: bool = True, legend_position: str = "bottom") -> str:
    if not chart_data:
        return '<div style="color:#999;padding:40px;text-align:center;">（無圖表資料）</div>'
    data_json = json.dumps(chart_data)
    legend_js = _build_legend_js(legend_show, legend_position)
    template = CHART_HTML_MAP.get(chart_type, CHART_HTML_MAP["bar"])
    return template.replace("__DATA__", data_json).replace("__COLORS__", COLORS).replace("__LEGEND__", legend_js)


def generate_report_html(
    title: str,
    chart_data: list,
    chart_type: str,
    analysis_summary: str,
    author: str,
    hints: str | None = None,
    legend_show: bool = True,
    legend_position: str = "bottom",
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    chart_html = build_chart_html(chart_data, chart_type, legend_show, legend_position)
    hints_block = HINTS_TEMPLATE.format(hints=hints) if hints else ""
    return HTML_TEMPLATE.format(
        title=title,
        chart_type=chart_type.upper(),
        chart_html=chart_html,
        analysis_summary=analysis_summary,
        author=author,
        timestamp=now,
        hints_block=hints_block,
        rechart_cdn=RECHART_CDN,
    )
