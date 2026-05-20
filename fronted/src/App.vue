<template>
  <div class="chat-page">
    <main class="chat-shell">
      <div class="chat-header">
        <div>
          <h1>数据问答</h1>
          <p>输入自然语言问题，查看执行进度和查询结果</p>
        </div>
        <span class="status-pill">NL2SQL</span>
      </div>

      <div ref="messagesEl" class="messages">
        <div v-if="messages.length === 0" class="empty-state">
          <h2>开始一次查询</h2>
          <p>例如：查询一下订单的营业额</p>
        </div>

        <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message-row', msg.role]"
        >
          <div v-if="msg.role === 'assistant'" class="avatar">AI</div>

          <div class="bubble">
            <div v-if="msg.type === 'text'">
              {{ msg.content }}
            </div>

            <div v-else-if="msg.type === 'steps'" class="steps">
              <div v-for="(step, sIdx) in msg.steps" :key="sIdx" class="step">
                <span class="dot" :class="step.status"></span>
                <span>{{ step.text }}</span>
              </div>
            </div>

            <div v-else-if="msg.type === 'table'" class="table-wrap">
              <table class="result-table">
                <thead>
                <tr>
                  <th v-for="col in msg.columns" :key="col">
                    {{ col }}
                  </th>
                </tr>
                </thead>
                <tbody>
                <tr v-for="(row, rIdx) in msg.rows" :key="rIdx">
                  <td v-for="col in msg.columns" :key="col">
                    {{ row[col] }}
                  </td>
                </tr>
                </tbody>
              </table>
            </div>

            <div v-else-if="msg.type === 'error'" class="error-text">
              {{ msg.content }}
            </div>
          </div>

          <div v-if="msg.role === 'user'" class="avatar user-avatar">我</div>
        </div>
      </div>

      <div class="input-wrapper">
        <div class="input-box">
          <input
              v-model="question"
              @keyup.enter="sendQuestion"
              placeholder="输入问题，例如：查询一下订单的营业额"
          />
          <button @click="sendQuestion" :disabled="loading || !question.trim()">
            {{ loading ? "执行中" : "发送" }}
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import {nextTick, ref} from "vue";

const API_URL = import.meta.env.VITE_API_URL || "/api/query";

const question = ref("");
const loading = ref(false);
const messages = ref([]);
const messagesEl = ref(null);

function scrollToBottom() {
  const el = messagesEl.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

async function sendQuestion() {
  if (!question.value || loading.value) return;

  const q = question.value;
  question.value = "";
  loading.value = true;

  messages.value.push({role: "user", type: "text", content: q});

  // steps 容器
  const stepIndex =
      messages.value.push({
        role: "assistant",
        type: "steps",
        steps: [],
      }) - 1;

  await nextTick();
  scrollToBottom();

  try {
    const response = await fetch(API_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
      },
      body: JSON.stringify({query: q}),
    });

    if (!response.ok) {
      throw new Error(`请求失败：${response.status} ${response.statusText}`);
    }

    if (!response.body) throw new Error("服务器未返回流");

    const reader = response.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let buffer = "";

    while (true) {
      const {value, done} = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, {stream: true});
      const events = buffer.split(/\r?\n\r?\n/);
      buffer = events.pop();

      for (const evt of events) {
        const payload = parseSseData(evt);
        if (!payload) continue;

        let data;
        try {
          data = JSON.parse(payload);
        } catch {
          continue;
        }

        const steps = messages.value[stepIndex].steps;

        // ✅ progress：完全按后端状态渲染
        if (data.type === "progress") {
          let step = steps.find((s) => s.text === data.step);

          if (!step) {
            step = {
              text: data.step,
              status: data.status,
            };
            steps.push(step);
          } else {
            step.status = data.status;
          }
        }

        // ✅ 表格结果
        else if (data.type === "result" && Array.isArray(data.data)) {
          messages.value.push({
            role: "assistant",
            type: data.data.length ? "table" : "text",
            columns: Object.keys(data.data[0] || {}),
            rows: data.data,
            content: data.data.length ? "" : "查询完成，暂无结果",
          });
        }

        // ✅ 错误
        else if (data.type === "error") {
          messages.value.push({
            role: "assistant",
            type: "error",
            content: data.message || "发生错误",
          });
        }

        await nextTick();
        scrollToBottom();
      }
    }

    if (buffer.trim()) {
      const payload = parseSseData(buffer);
      if (payload) {
        try {
          const data = JSON.parse(payload);
          if (data.type === "error") {
            messages.value.push({
              role: "assistant",
              type: "error",
              content: data.message || "发生错误",
            });
          }
        } catch {
          // Ignore partial or non-JSON trailing data.
        }
      }
    }
  } catch (e) {
    messages.value.push({
      role: "assistant",
      type: "error",
      content: e?.message || "请求失败",
    });
  } finally {
    loading.value = false;
    await nextTick();
    scrollToBottom();
  }
}

function parseSseData(eventText) {
  return eventText
      .split(/\r?\n/)
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.replace(/^data:\s?/, ""))
      .join("\n")
      .trim();
}
</script>
<style scoped>
:global(html),
:global(body) {
  height: 100%;
  margin: 0;
  background: #f6f7f9;
}

:global(body) {
  display: block !important;
  place-items: unset !important;
  color: #172033;
}

:global(#app) {
  height: 100%;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 !important;
}

.chat-page {
  height: 100%;
  overflow: hidden;
  background:
      linear-gradient(180deg, #f8fafc 0%, #ffffff 34%, #f5f7fb 100%);
}

.chat-shell {
  width: min(100%, 1080px);
  height: 100%;
  margin: 0 auto;
  display: grid;
  grid-template-rows: auto 1fr auto;
  padding: 28px 24px 22px;
  box-sizing: border-box;
}

.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 0 4px 18px;
}

.chat-header h1 {
  margin: 0;
  color: #101828;
  font-size: 24px;
  line-height: 1.25;
  font-weight: 700;
}

.chat-header p {
  margin: 6px 0 0;
  color: #667085;
  font-size: 14px;
}

.status-pill {
  flex: 0 0 auto;
  border: 1px solid #d6e4ff;
  border-radius: 999px;
  padding: 7px 12px;
  background: #eff6ff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0;
}

.messages {
  overflow-y: auto;
  min-height: 0;
  padding: 18px 4px 28px;
  scroll-behavior: smooth;
}

.empty-state {
  width: min(100%, 560px);
  margin: 12vh auto 0;
  text-align: center;
  color: #667085;
}

.empty-state h2 {
  margin: 0 0 10px;
  color: #1d2939;
  font-size: 28px;
  line-height: 1.2;
}

.empty-state p {
  margin: 0;
  font-size: 15px;
}

.message-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 18px;
}

.message-row.assistant {
  justify-content: flex-start;
}

.message-row.user {
  justify-content: flex-end;
}

.avatar {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  border-radius: 50%;
  background: #eef2f6;
  color: #475467;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  box-shadow: inset 0 0 0 1px rgba(16, 24, 40, 0.04);
}

.user-avatar {
  background: #dbeafe;
  color: #1d4ed8;
}

.bubble {
  max-width: min(760px, 72%);
  padding: 13px 16px;
  border-radius: 16px;
  background: #ffffff;
  border: 1px solid #eaecf0;
  color: #1d2939;
  font-size: 15px;
  line-height: 1.65;
  text-align: left;
  box-shadow: 0 8px 24px rgba(16, 24, 40, 0.06);
  overflow: hidden;
  overflow-wrap: anywhere;
}

.message-row.user .bubble {
  background: #1677ff;
  border-color: #1677ff;
  color: #ffffff;
  box-shadow: 0 10px 24px rgba(22, 119, 255, 0.2);
}

.steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 180px;
}

.step {
  display: flex;
  align-items: center;
  gap: 10px;
  color: #475467;
  font-size: 14px;
}

.dot {
  width: 10px;
  height: 10px;
  flex: 0 0 10px;
  border-radius: 50%;
  box-shadow: 0 0 0 3px rgba(102, 112, 133, 0.08);
}

.dot.running {
  background: #f59e0b;
}

.dot.success {
  background: #12b76a;
}

.dot.error {
  background: #f04438;
}

.table-wrap {
  max-width: 100%;
  overflow-x: auto;
}

.result-table {
  width: max-content;
  min-width: 100%;
  table-layout: auto;
  border-collapse: collapse;
  color: #1d2939;
}

.result-table th,
.result-table td {
  border: 1px solid #eaecf0;
  padding: 8px 12px;
  white-space: nowrap;
  font-size: 13px;
  text-align: left;
}

.result-table th {
  background: #f8fafc;
  font-weight: 600;
  position: sticky;
  top: 0;
  z-index: 1;
}

.error-text {
  color: #d92d20;
  font-weight: 600;
}

.input-wrapper {
  padding: 14px 0 0;
  background: linear-gradient(180deg, rgba(245, 247, 251, 0), #f5f7fb 35%);
}

.input-box {
  width: min(100%, 860px);
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 18px;
  background: #ffffff;
  border: 1px solid #d0d5dd;
  box-shadow: 0 18px 45px rgba(16, 24, 40, 0.12);
}

.input-box input {
  flex: 1;
  min-width: 0;
  height: 46px;
  border: none;
  outline: none;
  background: #f8fafc;
  border-radius: 12px;
  padding: 0 14px;
  color: #101828;
  font-size: 15px;
}

.input-box input::placeholder {
  color: #98a2b3;
}

.input-box button {
  flex: 0 0 auto;
  min-width: 88px;
  height: 46px;
  padding: 0 18px;
  border-radius: 12px;
  border: none;
  background: #1677ff;
  color: #fff;
  cursor: pointer;
  font-size: 15px;
  font-weight: 700;
  transition: background 0.2s ease, transform 0.2s ease;
}

.input-box button:hover:not(:disabled) {
  background: #0958d9;
  transform: translateY(-1px);
}

.input-box button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .chat-shell {
    padding: 18px 14px 14px;
  }

  .chat-header {
    align-items: flex-start;
    padding-bottom: 12px;
  }

  .chat-header h1 {
    font-size: 20px;
  }

  .chat-header p {
    font-size: 13px;
  }

  .status-pill {
    display: none;
  }

  .messages {
    padding-top: 10px;
  }

  .avatar {
    width: 32px;
    height: 32px;
    flex-basis: 32px;
    font-size: 12px;
  }

  .bubble {
    max-width: calc(100% - 42px);
    padding: 11px 13px;
    border-radius: 14px;
    font-size: 14px;
  }

  .input-box {
    border-radius: 16px;
    padding: 8px;
  }

  .input-box input {
    height: 42px;
  }

  .input-box button {
    min-width: 72px;
    height: 42px;
    padding: 0 14px;
  }
}
</style>
