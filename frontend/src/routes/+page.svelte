<script lang="ts">
  type Message = {
    role: 'user' | 'assistant';
    text: string;
  };

  let input = $state('');
  let messages = $state<Message[]>([]);
  let sending = $state(false);
  let error = $state('');

  async function sendMessage(event: SubmitEvent) {
    event.preventDefault();

    const question = input.trim();
    if (!question || sending) return;

    messages = [...messages, { role: 'user', text: question }];
    input = '';
    error = '';
    sending = true;

    try {
      const response = await fetch('http://127.0.0.1:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: question })
      });

      if (!response.ok) {
        throw new Error(`Backend returned HTTP ${response.status}`);
      }

      const data: { answer: string } = await response.json();
      messages = [...messages, { role: 'assistant', text: data.answer }];
    } catch (cause) {
      error = cause instanceof Error ? cause.message : 'Could not send the message.';
    } finally {
      sending = false;
    }
  }
</script>

<svelte:head>
  <title>Bundle Data Assistant</title>
</svelte:head>

<main>
  <h1>Bundle Data Assistant</h1>
  <p>Ask a question about orders.</p>

  <section class="messages" aria-label="Chat messages">
    {#each messages as message}
      <p class:user={message.role === 'user'}>
        <strong>{message.role === 'user' ? 'You' : 'Assistant'}:</strong>
        {message.text}
      </p>
    {/each}
  </section>

  {#if error}
    <p class="error" role="alert">{error}</p>
  {/if}

  <form onsubmit={sendMessage}>
    <input
      aria-label="Your question"
      placeholder="Show orders by provider..."
      bind:value={input}
    />

    <button type="submit" disabled={sending}>
      {sending ? 'Sending...' : 'Send'}
    </button>
  </form>
</main>

<style>
  main {
    max-width: 680px;
    margin: 3rem auto;
    padding: 1rem;
    font-family: system-ui, sans-serif;
  }

  .messages {
    min-height: 240px;
    padding: 1rem;
    border: 1px solid #ccc;
    border-radius: 8px;
  }

  .messages p {
    padding: 0.75rem;
    background: #f0f3f8;
    border-radius: 8px;
  }

  .messages p.user {
    background: #e1f0ff;
  }

  form {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  input {
    flex: 1;
    min-width: 0;
    padding: 0.75rem;
  }

  button {
    padding: 0.75rem 1rem;
  }

  .error {
    color: darkred;
  }
</style>