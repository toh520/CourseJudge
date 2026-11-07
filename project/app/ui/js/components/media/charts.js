/**
 * 文件名: charts.js
 * 功能描述: ECharts 图表封装。提供分数段柱状图、题目通过率柱状图与薄弱知识点
 *          横向条形图；图表库缺失或容器销毁时安全降级。
 */

const PALETTE = {
  text: '#93a1b8',
  textDim: '#617089',
  line: '#222c3d',
  accent: '#4c8dff',
  success: '#3fb950',
  warning: '#d29922',
  danger: '#f85149',
  purple: '#bc8cff',
};

function mount(container) {
  if (!window.echarts) {
    container.innerHTML = '<div class="chart-fallback">图表库未加载</div>';
    return null;
  }
  if (!container.isConnected) return null;
  container.dataset.chart = '1';
  const existing = window.echarts.getInstanceByDom(container);
  if (existing) existing.dispose();
  return window.echarts.init(container, null, { renderer: 'canvas' });
}

function baseGrid() {
  return { left: 14, right: 18, top: 28, bottom: 12, containLabel: true };
}

function axisStyle() {
  return {
    axisLine: { lineStyle: { color: PALETTE.line } },
    axisTick: { show: false },
    axisLabel: { color: PALETTE.text, fontSize: 11 },
    splitLine: { lineStyle: { color: 'rgba(34,44,61,.55)' } },
  };
}

/**
 * 分数段分布柱状图
 * @param {HTMLElement} container
 * @param {Array<{band:string,count:number}>} bands
 */
export function renderScoreBands(container, bands) {
  const chart = mount(container);
  if (!chart) return;
  const data = bands || [];
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: '#151b27', borderColor: PALETTE.line, textStyle: { color: '#e8eefb', fontSize: 12 } },
    grid: baseGrid(),
    xAxis: { type: 'category', data: data.map((item) => item.band), ...axisStyle(), splitLine: { show: false } },
    yAxis: { type: 'value', minInterval: 1, ...axisStyle() },
    series: [{
      type: 'bar',
      data: data.map((item, index) => ({
        value: item.count,
        itemStyle: {
          color: [PALETTE.success, PALETTE.accent, PALETTE.warning, PALETTE.danger][index] || PALETTE.accent,
          borderRadius: [4, 4, 0, 0],
        },
      })),
      barMaxWidth: 42,
      label: { show: true, position: 'top', color: PALETTE.text, fontSize: 11 },
    }],
  });
}

/**
 * 各题通过率漏斗图
 * @param {HTMLElement} container
 * @param {Array<{problem_title:string,ac_rate:number}>} stats
 */
export function renderProblemRates(container, stats) {
  const chart = mount(container);
  if (!chart) return;
  const data = (stats || [])
    .slice(0, 8)
    .map((item) => ({ name: item.problem_title, value: item.ac_rate }))
    .sort((a, b) => b.value - a.value);

  if (!data.length) {
    container.innerHTML = '<div class="chart-fallback">暂无题目通过率数据</div>';
    chart.dispose();
    return;
  }

  const colors = [PALETTE.success, PALETTE.accent, PALETTE.warning, PALETTE.danger, PALETTE.purple];
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#151b27',
      borderColor: PALETTE.line,
      textStyle: { color: '#e8eefb', fontSize: 12 },
      formatter: '{b}<br/>通过率 {c}%',
    },
    series: [{
      type: 'funnel',
      left: '6%',
      right: '6%',
      top: 12,
      bottom: 8,
      min: 0,
      max: 100,
      minSize: '18%',
      maxSize: '100%',
      sort: 'descending',
      gap: 4,
      label: {
        show: true,
        position: 'inside',
        color: '#e8eefb',
        fontSize: 11,
        formatter: (params) => {
          const name = params.name.length > 12 ? `${params.name.slice(0, 12)}…` : params.name;
          return `${name}  ${params.value}%`;
        },
      },
      labelLine: { show: false },
      itemStyle: { borderColor: '#151b27', borderWidth: 1 },
      emphasis: { label: { fontSize: 12, fontWeight: 600 } },
      data: data.map((item, index) => ({
        ...item,
        itemStyle: { color: colors[index % colors.length] },
      })),
    }],
  });
}

/**
 * 薄弱知识点雷达图 (少于 3 项时回退为横向条形图)
 * @param {HTMLElement} container
 * @param {Array<{tag:string,fail_rate:number,failed_students:number}>} tags
 */
export function renderWeakTags(container, tags) {
  const data = (tags || []).slice(0, 6);
  if (!data.length) {
    container.innerHTML = '<div class="chart-fallback">暂无可统计的薄弱知识点</div>';
    return;
  }

  const chart = mount(container);
  if (!chart) return;

  if (data.length < 3) {
    const reversed = data.slice().reverse();
    chart.setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, backgroundColor: '#151b27', borderColor: PALETTE.line, textStyle: { color: '#e8eefb', fontSize: 12 } },
      grid: { left: 10, right: 42, top: 16, bottom: 10, containLabel: true },
      xAxis: { type: 'value', min: 0, max: 100, ...axisStyle(), axisLabel: { color: PALETTE.text, fontSize: 10, formatter: '{value}%' } },
      yAxis: {
        type: 'category',
        data: reversed.map((item) => item.tag),
        axisLine: { lineStyle: { color: PALETTE.line } },
        axisTick: { show: false },
        axisLabel: { color: PALETTE.text, fontSize: 11 },
      },
      series: [{
        type: 'bar',
        data: reversed.map((item) => ({
          value: item.fail_rate,
          itemStyle: { color: item.fail_rate >= 50 ? PALETTE.danger : PALETTE.warning, borderRadius: [0, 4, 4, 0] },
        })),
        barMaxWidth: 22,
        label: { show: true, position: 'right', color: PALETTE.text, fontSize: 10, formatter: '{c}%' },
      }],
    });
    return;
  }

  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: '#151b27',
      borderColor: PALETTE.line,
      textStyle: { color: '#e8eefb', fontSize: 12 },
    },
    radar: {
      indicator: data.map((item) => ({
        name: item.tag.length > 12 ? `${item.tag.slice(0, 12)}…` : item.tag,
        max: 100,
      })),
      radius: '62%',
      center: ['50%', '54%'],
      axisName: { color: PALETTE.text, fontSize: 10 },
      splitLine: { lineStyle: { color: 'rgba(34,44,61,.8)' } },
      splitArea: { areaStyle: { color: ['rgba(76,141,255,.03)', 'rgba(76,141,255,.06)'] } },
      axisLine: { lineStyle: { color: 'rgba(34,44,61,.8)' } },
    },
    series: [{
      type: 'radar',
      symbolSize: 5,
      data: [{
        value: data.map((item) => item.fail_rate),
        name: '失分率',
        lineStyle: { color: PALETTE.danger, width: 2 },
        itemStyle: { color: PALETTE.danger },
        areaStyle: { color: 'rgba(248,81,73,.24)' },
      }],
    }],
  });
}

/**
 * 销毁容器内所有 ECharts 实例
 * @param {HTMLElement} root
 */
export function disposeCharts(root) {
  if (!root || !window.echarts) return;
  root.querySelectorAll('[data-chart]').forEach((node) => {
    const instance = window.echarts.getInstanceByDom(node);
    if (instance) instance.dispose();
  });
}

/**
 * 窗口尺寸变化时重绘
 * @param {HTMLElement} root
 */
export function resizeCharts(root) {
  if (!root || !window.echarts) return;
  root.querySelectorAll('[data-chart]').forEach((node) => {
    const instance = window.echarts.getInstanceByDom(node);
    if (instance) instance.resize();
  });
}