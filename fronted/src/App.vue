<template>
  <div class="chat-page">
    <aside class="session-sidebar">
      <div class="sidebar-brand">
        <div class="brand-mark">数</div>
        <div>
          <strong>掌柜问数</strong>
          <span>会话记录</span>
        </div>
      </div>

      <button class="sidebar-new-button" type="button" :disabled="loading" @click="createNewConversation">
        <span aria-hidden="true">+</span>
        新建对话
      </button>

      <div class="session-list" aria-label="会话列表">
        <div v-if="sessionsLoading" class="session-placeholder">加载会话中...</div>
        <div v-else-if="sessions.length === 0" class="session-placeholder">暂时没有对话</div>
        <div
            v-for="session in sessions"
            :key="session.session_id"
            :class="['session-item', {active: session.session_id === sessionId}]"
            :aria-current="session.session_id === sessionId ? 'page' : undefined"
            role="button"
            tabindex="0"
            @click="switchConversation(session.session_id)"
            @keydown.enter="switchConversation(session.session_id)"
        >
          <span class="session-title">{{ session.title }}</span>
          <span class="session-meta">{{ session.turn_count }} 次问数</span>
          <button
              type="button"
              class="session-delete"
              title="删除会话"
              aria-label="删除会话"
              :disabled="loading"
              @click.stop="deleteConversation(session.session_id)"
          >x</button>
        </div>
      </div>
    </aside>

    <main class="chat-shell">
      <div class="chat-header">
        <div>
          <h1>数据问答</h1>
          <p>输入自然语言问题，查看执行进度和查询结果</p>
        </div>
        <div class="header-actions">
          <button
              type="button"
              class="new-chat-button"
              :disabled="loading"
              @click="createNewConversation"
          >
            新对话
          </button>
          <span class="status-pill">NL2SQL</span>
        </div>
      </div>

      <div class="conversation-panel" :class="{ 'is-switching': isSwitching }">
        <Transition name="conversation" mode="out-in">
          <div :key="conversationVersion" ref="messagesEl" class="messages">
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
              <div v-if="msg.resolvedQuery" class="resolved-query">
                <span>已理解为</span>
                {{ msg.resolvedQuery }}
              </div>
            </div>

            <div v-else-if="msg.type === 'context'" class="resolved-query restored-context">
              <span>已理解为</span>
              {{ msg.content }}
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
        </Transition>

        <div v-if="isSwitching" class="conversation-switching" aria-live="polite">
          <span class="switching-spinner" aria-hidden="true"></span>
          正在打开会话
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
import {nextTick, onMounted, ref} from "vue";

const API_URL = import.meta.env.VITE_API_URL || "/api/query";
const SESSION_API_URL = API_URL.replace(/\/query$/, "/sessions");

const question = ref("");
const loading = ref(false);
const messages = ref([]);
const messagesEl = ref(null);
const sessionId = ref(null);
const sessions = ref([]);
const sessionsLoading = ref(true);
const isSwitching = ref(false);
const conversationVersion = ref(0);

function scrollToBottom() {
  const el = messagesEl.value;
  if (!el) return;
  el.scrollTop = el.scrollHeight;
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`请求失败：${response.status}`);
  return response.status === 204 ? null : response.json();
}

async function loadSessions() {
  const data = await requestJson(SESSION_API_URL);
  sessions.value = data.sessions || [];
}

async function createNewConversation() {
  if (loading.value) return;
  const session = await requestJson(SESSION_API_URL, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({title: "新对话"}),
  });
  question.value = "";
  messages.value = [];
  sessionId.value = session.session_id;
  conversationVersion.value += 1;
  sessions.value = [{...session, turn_count: 0}, ...sessions.value];
  await nextTick();
  scrollToBottom();
}

async function switchConversation(nextSessionId) {
  if (loading.value || isSwitching.value || nextSessionId === sessionId.value) return;
  isSwitching.value = true;
  try {
    const data = await requestJson(`${SESSION_API_URL}/${nextSessionId}`);
    sessionId.value = nextSessionId;
    messages.value = data.messages || [];
    conversationVersion.value += 1;
    question.value = "";
    await nextTick();
    scrollToBottom();
  } finally {
    isSwitching.value = false;
  }
}

async function deleteConversation(targetSessionId) {
  if (loading.value) return;
  await requestJson(`${SESSION_API_URL}/${targetSessionId}`, {method: "DELETE"});
  sessions.value = sessions.value.filter((session) => session.session_id !== targetSessionId);
  if (sessionId.value !== targetSessionId) return;
  if (sessions.value.length > 0) {
    await switchConversation(sessions.value[0].session_id);
  } else {
    await createNewConversation();
  }
}

async function sendQuestion() {
  if (!question.value || loading.value) return;
  if (!sessionId.value) await createNewConversation();

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
        resolvedQuery: "",
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
      body: JSON.stringify({
        query: q,
        session_id: sessionId.value,
      }),
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

        if (data.type === "session" && data.session_id) {
          sessionId.value = data.session_id;
        }

        // ✅ progress：完全按后端状态渲染
        else if (data.type === "progress") {
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

        else if (data.type === "context_resolved") {
          messages.value[stepIndex].resolvedQuery = data.query || "";
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
    await loadSessions();
    await nextTick();
    scrollToBottom();
  }
}

onMounted(async () => {
  try {
    await loadSessions();
    if (sessions.value.length > 0) {
      await switchConversation(sessions.value[0].session_id);
    } else {
      await createNewConversation();
    }
  } catch (error) {
    messages.value = [{role: "assistant", type: "error", content: "会话服务暂不可用"}];
  } finally {
    sessionsLoading.value = false;
  }
});

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
  display: grid;
  grid-template-columns: 264px minmax(0, 1fr);
  background: #f6f7f9;
}

.session-sidebar {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 20px 12px 14px;
  background: #ffffff;
  border-right: 1px solid #e4e7ec;
  box-sizing: border-box;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 8px 18px;
}

.brand-mark {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  background: #1677ff;
  color: #ffffff;
  font-size: 16px;
  font-weight: 700;
  border-radius: 7px;
}

.sidebar-brand strong,
.sidebar-brand span {
  display: block;
}

.sidebar-brand strong {
  color: #1d2939;
  font-size: 15px;
}

.sidebar-brand span {
  margin-top: 2px;
  color: #98a2b3;
  font-size: 12px;
}

.sidebar-new-button {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  width: 100%;
  height: 38px;
  margin-bottom: 14px;
  border: 1px solid #c8d7f1;
  border-radius: 7px;
  background: #eff6ff;
  color: #175cd3;
  cursor: pointer;
  font-size: 13px;
  font-weight: 700;
}

.sidebar-new-button span {
  font-size: 19px;
  font-weight: 400;
  line-height: 1;
}

.sidebar-new-button:hover:not(:disabled) {
  background: #dbeafe;
}

.sidebar-new-button:disabled,
.session-delete:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.session-list {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  padding: 0 2px;
  scrollbar-gutter: stable;
}

.session-placeholder {
  padding: 28px 8px;
  color: #98a2b3;
  font-size: 13px;
  text-align: center;
}

.session-item {
  position: relative;
  display: block;
  min-width: 0;
  margin-bottom: 4px;
  padding: 10px 32px 10px 10px;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #475467;
  cursor: pointer;
  outline: none;
}

.session-item:hover,
.session-item:focus-visible {
  background: #f8fafc;
  border-color: #eaecf0;
}

.session-item.active {
  background: #eaf2ff;
  border-color: #c7ddff;
  color: #175cd3;
}

.session-title,
.session-meta {
  display: block;
}

.session-title {
  overflow: hidden;
  color: inherit;
  font-size: 13px;
  font-weight: 600;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-meta {
  margin-top: 4px;
  color: #98a2b3;
  font-size: 11px;
}

.session-delete {
  position: absolute;
  top: 50%;
  right: 7px;
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: #98a2b3;
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
  opacity: 0;
  transform: translateY(-50%);
}

.session-item:hover .session-delete,
.session-item:focus-within .session-delete,
.session-item.active .session-delete {
  opacity: 1;
}

.session-delete:hover:not(:disabled) {
  background: #fee4e2;
  color: #d92d20;
}

.chat-shell {
  width: min(100%, 1080px);
  height: 100%;
  min-height: 0;
  margin: 0 auto;
  display: grid;
  grid-template-rows: auto 1fr auto;
  padding: 28px 24px 22px;
  box-sizing: border-box;
  overflow: hidden;
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 0 0 auto;
}

.new-chat-button {
  height: 34px;
  padding: 0 12px;
  border: 1px solid #d0d5dd;
  border-radius: 8px;
  background: #ffffff;
  color: #344054;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
}

.new-chat-button:hover:not(:disabled) {
  border-color: #98a2b3;
  background: #f8fafc;
}

.new-chat-button:disabled {
  opacity: 0.45;
  cursor: not-allowed;
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

.conversation-panel {
  position: relative;
  min-height: 0;
  overflow: hidden;
}

.messages {
  height: 100%;
  overflow-y: auto;
  min-height: 0;
  padding: 18px 4px 28px;
  scroll-behavior: smooth;
  scrollbar-gutter: stable;
  scrollbar-width: thin;
  scrollbar-color: #b8c2d1 transparent;
}

.messages::-webkit-scrollbar,
.session-list::-webkit-scrollbar {
  width: 9px;
}

.messages::-webkit-scrollbar-thumb,
.session-list::-webkit-scrollbar-thumb {
  border: 3px solid transparent;
  border-radius: 999px;
  background-clip: padding-box;
  background-color: #b8c2d1;
}

.messages::-webkit-scrollbar-track,
.session-list::-webkit-scrollbar-track {
  background: transparent;
}

.conversation-switching {
  position: absolute;
  top: 18px;
  left: 50%;
  z-index: 3;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid #d0d5dd;
  border-radius: 7px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 8px 18px rgba(16, 24, 40, 0.12);
  color: #475467;
  font-size: 13px;
  font-weight: 600;
  transform: translateX(-50%);
}

.switching-spinner {
  width: 13px;
  height: 13px;
  border: 2px solid #c7ddff;
  border-top-color: #1677ff;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}

.conversation-panel.is-switching .messages {
  opacity: 0.42;
  transform: translateY(4px);
}

.conversation-enter-active,
.conversation-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.conversation-enter-from,
.conversation-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
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

.resolved-query {
  margin-top: 4px;
  padding: 8px 10px;
  border-left: 3px solid #84adff;
  background: #f2f7ff;
  color: #344054;
  font-size: 12px;
  line-height: 1.55;
}

.resolved-query span {
  margin-right: 6px;
  color: #175cd3;
  font-weight: 700;
}

.restored-context {
  margin: 0;
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
  .chat-page {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr);
  }

  .session-sidebar {
    min-height: 0;
    padding: 10px 12px;
    border-right: none;
    border-bottom: 1px solid #e4e7ec;
  }

  .sidebar-brand {
    display: none;
  }

  .sidebar-new-button {
    display: none;
  }

  .session-list {
    display: flex;
    gap: 6px;
    overflow-x: auto;
    overflow-y: hidden;
    padding: 0;
  }

  .session-item {
    flex: 0 0 148px;
    margin: 0;
    padding-right: 26px;
  }

  .session-placeholder {
    padding: 6px 8px;
    text-align: left;
  }

  .session-delete {
    opacity: 1;
  }

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
