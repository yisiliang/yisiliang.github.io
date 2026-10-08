'use strict';
// Deliberately hand-set teaching matrices, not trained model parameters.
const queryInputs = [document.querySelector('#q0'), document.querySelector('#q1')];
const causalInput = document.querySelector('#causal');
const output = document.querySelector('#lab-result');
function updateAttention() {
  const q = queryInputs.map(input => Number(input.value));
  const keys = [[1, 0], [0, 1], [1, 1]];
  const values = [[2, 0], [0, 1], [2, 1]];
  const scores = keys.map(k => (q[0] * k[0] + q[1] * k[1]) / Math.sqrt(2));
  const allowed = scores.map((_, i) => !causalInput.checked || i === 0);
  const max = Math.max(...scores.filter((_, i) => allowed[i]));
  const exps = scores.map((s, i) => allowed[i] ? Math.exp(s - max) : 0);
  const sum = exps.reduce((a, b) => a + b, 0);
  const weights = exps.map(v => v / sum);
  const result = [0, 1].map(j => weights.reduce((acc, w, i) => acc + w * values[i][j], 0));
  const fmt = xs => `[${xs.map(x => x.toFixed(6)).join(', ')}]`;
  output.textContent = `查询 q = ${fmt(q)}\n缩放分数 = ${fmt(scores)}\n合法位置 = ${allowed.map((a, i) => a ? i : '屏蔽').join(', ')}\n注意力权重 = ${fmt(weights)}\n权重和 = ${weights.reduce((a, b) => a + b, 0).toFixed(6)}\n输出向量 = ${fmt(result)}`;
}
[...queryInputs, causalInput].forEach(input => input.addEventListener('input', updateAttention));
updateAttention();
