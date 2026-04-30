from datetime import datetime

RECHART_CDN = """<script src="https://unpkg.com/recharts@2.15.0/umd/Recharts.js"></script>"""

COLORS = [
    "#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#8884D8",
    "#82CA9D", "#FFC658", "#8DD1E1", "#A4DE6C", "#D0ED57",
]


def generate_report_html(
    title: str,
    author: str,
    chart_code: str,
    analysis: str,
    chart_type: str = "mixed",
) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    chart_components = generate_chart_components(chart_code, chart_type)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {RECHART_CDN}
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
            min-height: 400px;
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
        .analysis-content h3 {{
            color: #333;
            margin-top: 16px;
            margin-bottom: 8px;
        }}
        .analysis-content ul {{
            margin-left: 24px;
            margin-bottom: 12px;
        }}
        .analysis-content li {{
            margin-bottom: 4px;
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
            <span class="badge">{chart_type.upper()}</span>
            製作日期：{now} | 作者：{author}
        </div>
    </header>

    <main class="container">
        <section class="chart-section">
            <h2 class="chart-title">📊 資料視覺化</h2>
            <div class="chart-container">
                {chart_components}
            </div>
        </section>

        <section class="analysis-section">
            <h2 class="analysis-title">📝 資料分析報告</h2>
            <div class="analysis-content">
                {analysis}
            </div>
        </section>
    </main>

    <footer class="footer">
        <p>此報告由 Report Agent 自動生成 | 資料僅在本地處理，不上傳外部服務</p>
    </footer>
</body>
</html>"""
    return html


def generate_chart_components(chart_code: str, chart_type: str) -> str:
    """Parse LLM generated chart code and wrap in proper React component."""
    if not chart_code or chart_code.strip() == "":
        return '<div style="color:#999;padding:40px;text-align:center;">（無圖表資料）</div>'

    return f"""
    <script>
        const data = {chart_code};
        const COLORS = {COLORS};
    </script>
    <div id="chart"></div>
    <script>
        // Chart rendering will be handled by the embedded Recharts
    </script>
    """


def wrap_recharts_component(chart_type: str, data_var: str, title: str = "") -> str:
    """Wrap chart code in proper React component structure."""
    if chart_type == "pie":
        return f'''
        <div style={{display:"flex",flexDirection:"column",alignItems:"center"}}>
          <h3 style={{marginBottom:"16px",color:"#333"}}>{title}</h3>
          <PieChart width={700} height={350}>
            <Pie
              data={{{data_var}}}
              cx="50%"
              cy="50%"
              labelLine={{false}}
              label={{{{name, percent}}}} => `${{name}}: ${{(percent * 100).toFixed(1)}}%`}}
              outerRadius={{130}}
              fill="#8884d8"
              dataKey="value"
            >
              {{{data_var}.map((entry, index) => (
                <Cell key={{`cell-${{index}}`}} fill={{COLORS[index % COLORS.length]}} />
              ))}}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        </div>'''
    elif chart_type == "bar":
        return f'''
        <div style={{display:"flex",flexDirection:"column",alignItems:"center"}}>
          <h3 style={{marginBottom:"16px",color:"#333"}}>{title}</h3>
          <BarChart width={700} height={350} data={{{data_var}}}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="value" fill="#8884d8" />
          </BarChart>
        </div>'''
    elif chart_type == "line":
        return f'''
        <div style={{display:"flex",flexDirection:"column",alignItems:"center"}}>
          <h3 style={{marginBottom:"16px",color:"#333"}}>{title}</h3>
          <LineChart width={700} height={350} data={{{data_var}}}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line type="monotone" dataKey="value" stroke="#8884d8" strokeWidth={{2}} />
          </LineChart>
        </div>'''
    elif chart_type == "area":
        return f'''
        <div style={{display:"flex",flexDirection:"column",alignItems:"center"}}>
          <h3 style={{marginBottom:"16px",color:"#333"}}>{title}</h3>
          <AreaChart width={700} height={350} data={{{data_var}}}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Area type="monotone" dataKey="value" stroke="#8884d8" fill="#8884d8" fillOpacity={{0.3}} />
          </AreaChart>
        </div>'''
    else:
        return f'''
        <div style={{display:"flex",flexDirection:"column",alignItems:"center"}}>
          <h3 style={{marginBottom:"16px",color:"#333"}}>{title}</h3>
          <BarChart width={700} height={350} data={{{data_var}}}>
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="value" fill="#8884d8" />
          </BarChart>
        </div>'''
