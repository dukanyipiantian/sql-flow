// static/js/app.js
let simulation;

document.addEventListener('DOMContentLoaded', function() {
    const sqlInput = document.getElementById('sql-input');
    const parseBtn = document.getElementById('parse-btn');
    const tablesList = document.getElementById('tables-list');
    const columnsList = document.getElementById('columns-list');
    const joinsList = document.getElementById('joins-list');
    const loading = document.getElementById('loading');
    const errorMsg = document.getElementById('error-message');
    const svg = d3.select("#lineage-graph");

    // 示例SQL快捷输入（开发调试用）
    sqlInput.value = `SELECT u.id, o.order_date, p.product_name
FROM users u
JOIN orders o ON u.id = o.user_id
JOIN products p ON o.product_id = p.id
WHERE u.status = 'active';`;

    parseBtn.addEventListener('click', async function() {
        const sql = sqlInput.value.trim();

        if (!sql) {
            showError('请输入SQL语句');
            return;
        }

        // 清空之前的结果
        clearResults();

        try {
            loading.style.display = 'block';
            parseBtn.disabled = true;

            const response = await fetch('/api/parse', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ sql })
            });

            const { success, data, error } = await response.json();
            if (success) {
                console.log('API返回的data对象:', JSON.stringify(data, null, 2));  // 关键调试语句
                renderResults(data);
                drawLineage(data);
            } else {
                showError(error || '解析失败');
            }
        } catch (err) {
            showError('网络请求失败: ' + err.message);
        } finally {
            loading.style.display = 'none';
            parseBtn.disabled = false;
        }
    });

    function clearResults() {
        tablesList.innerHTML = '';
        columnsList.innerHTML = '';
        joinsList.innerHTML = '';
        svg.selectAll("*").remove();
        hideError();
    }

    function renderResults(data) {
        // 渲染表
//        console.log(data.tables);
        if (data.tables && data.tables.length > 0) {
            tablesList.innerHTML = data.tables.map(table =>
                `<li><span class="table-name">${table}</span></li>`
            ).join('');
        } else {
            tablesList.innerHTML = '<li>未检测到表</li>';
        }

        // 渲染字段
        if (data.columns && data.columns.length > 0) {
            columnsList.innerHTML = data.columns.map(column => {
                const icon = column.endsWith('.*') ? '🌐' : '🔹';
                return `<li>${icon} ${column}</li>`;
            }).join('');
        } else {
            columnsList.innerHTML = '<li>未检测到字段</li>';
        }

        // 渲染JOIN关系
        if (data.joins && data.joins.length > 0) {
            joinsList.innerHTML = data.joins.map(join =>
                `<li>
                    <span class="table-name">${join.left_table}</span>.<span class="column-name">${join.left_column}</span>
                    →
                    <span class="table-name">${join.right_table}</span>.<span class="column-name">${join.right_column}</span>
                </li>`
            ).join('');
        } else {
            joinsList.innerHTML = '<li>未检测到JOIN关系</li>';
        }
    }

    function drawLineage(data) {
    if (!data?.graph) {
        console.warn('缺少graph数据');
        return;
    }

    const width = svg.node().getBoundingClientRect().width;
    const height = 600;
    svg.selectAll("*").remove();

    // 规范化数据
    const graph = {
        nodes: data.graph.nodes || [],
        links: data.graph.links || []
    };

    // 验证节点和链接
    const nodeIds = new Set(graph.nodes.map(n => n.id));
    const invalidLinks = graph.links.filter(link =>
        !nodeIds.has(link.source) || !nodeIds.has(link.target)
    );

    console.log(invalidLinks);

    if (invalidLinks.length > 0) {
        console.error('无效的链接:', invalidLinks);
        graph.links = graph.links.filter(link =>
            nodeIds.has(link.source) && nodeIds.has(link.target)
        );
    }

    // 创建力导向图
    simulation = d3.forceSimulation(graph.nodes)
        .force("link", d3.forceLink(graph.links)
            .id(d => d.id)
            .distance(100)
        )
        .force("charge", d3.forceManyBody().strength(-500))
        .force("x", d3.forceX(width/2).strength(0.05))
        .force("y", d3.forceY(height/2).strength(0.05))
        .force("collision", d3.forceCollide().radius(d => d.type === 'table' ? 25 : 15));

    // 绘制连线
    const link = svg.append("g")
        .selectAll("line")
        .data(graph.links)
        .join("line")
        .attr("class", d => `link-${d.type}`)
        .attr("stroke-width", 2);

    // 绘制节点
    const node = svg.append("g")
        .selectAll("circle")
        .data(graph.nodes)
        .join("g")
        .call(drag(simulation));

    node.append("circle")
        .attr("class", d => `node-${d.type}`)
        .attr("r", d => d.type === "table" ? 15 : 10);

    node.append("text")
        .attr("dy", d => d.type === "table" ? 25 : 20)
        .text(d => d.name)
        .attr("text-anchor", "middle");

    simulation.on("tick", () => {
        link.attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        node.attr("transform", d => `translate(${d.x},${d.y})`);
    });
}

    function drag(simulation) {
        return d3.drag()
            .on("start", (event, d) => {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            })
            .on("drag", (event, d) => {
                d.fx = event.x;
                d.fy = event.y;
            })
            .on("end", (event, d) => {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            });
    }

    function showError(message) {
        errorMsg.textContent = message;
        errorMsg.style.display = 'block';
    }

    function hideError() {
        errorMsg.style.display = 'none';
    }
});