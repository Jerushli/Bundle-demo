
<script lang="ts">

  import { onMount } from 'svelte';

  import { Bar, Line, Pie } from 'svelte-chartjs';

  import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    BarElement,
    LineElement,
    PointElement,
    ArcElement,
    Title,
    Tooltip,
    Legend
  } from 'chart.js';

  // Avoid passing an undefined registry item to Chart.js (which throws while
  // reading its `name`); this also keeps startup safe across Chart.js builds.
  const chartRegistryItems = [
    CategoryScale,
    LinearScale,
    BarElement,
    LineElement,
    PointElement,
    ArcElement,
    Title,
    Tooltip,
    Legend
  ].filter(
    (item): item is NonNullable<typeof item> =>
      item != null && typeof (item as { id?: unknown }).id === 'string'
  );

  ChartJS.register(...chartRegistryItems);


  // ------------------------------------------
  // Authentication - Login page
  //-------------------------------------------

  let loginUsername = $state('');
  let loginPassword = $state('');
  let authToken = $state<string | null>(null);
  let loginError = $state('');
  let loggingIn = $state(false);

  const AUTH_TOKEN_KEY = 'bundle-data-assistant-token';

  // ------------------------------------------

  // TYPES

  // ------------------------------------------



  type Row = Record<string, string | number | null>;

  

  type Message = {

    id: string;

    role: 'user' | 'assistant';

    text: string;

    rows?: Row[];

    group_by?: string;

    source?: 'orders' | 'financials';

    metric?: string;

  };



  type Conversation = {

    id: string;

    title: string;

    messages: Message[];

    context? : AnalysisContext | null;

  };

  type AnalysisContext = {
    metric: string | null;
    group_by: string | null;
    entity: string | null;

    year?: number | null;
    country?: string | null;
    product?: string | null;
    segment?: string | null;

   }; 

  type ChatResponse = {

    answer: string;

    rows?: Row[];

    group_by?: string;

    source?: 'orders' | 'financials';

    metric?: string;

    year?: number | null;
    country?: string | null;
    product?: string | null;
    segment?: string | null;

  };



  // ------------------------------------------

  // APPLICATION STATE

  // ------------------------------------------



  let input = $state('');



  let conversations = $state<Conversation[]>([]);



  let activeConversationId = $state<string | null>(null);



  let sending = $state(false);



  let error = $state('');



  let sidebarOpen = $state(false);


  let lastAnalysis = $state<{
    metric?: string | null;
    group_by?: string | null;
    rows?: Row[] | null;
  } | null>(null);


  let chatContainer = $state<HTMLDivElement>();



  const API_URL = '/api/chat';



  const STORAGE_KEY = 'bundle-data-assistant-conversations';

  const ACTIVE_KEY = 'bundle-data-assistant-active-chat';



  // ------------------------------------------

  // SUGGESTED QUESTIONS

  // ------------------------------------------



  const suggestions = [
  'Which country generated the highest sales?',
  'Which product made the most profit?',
  'What was total profit in 2014?',
  'Show sales by segment',
  'Show sales by month',
  'How many units were sold by product?'
];



  // ------------------------------------------

  // HELPERS

  // ------------------------------------------



  async function login() {
  loginError = '';
  loggingIn = true;

  try {
    const response = await fetch('/api/login', {
      method: 'POST',

      headers: {
       'Content-Type': 'application/json'
    },

      body: JSON.stringify({
        username: loginUsername.trim(),
        password: loginPassword
      })
    });

    if (!response.ok) {
      throw new Error(
        'Invalid username or password.'
      );
    }

    const data = await response.json();

    if (!data.access_token) {
      throw new Error(
        'Login response did not include a token.'
      );
    }

    authToken = data.access_token;

    localStorage.setItem(
      AUTH_TOKEN_KEY,
      data.access_token
    );

    loginPassword = '';
  } catch (cause) {
    loginError =
      cause instanceof Error
        ? cause.message
        : 'Login failed.';
  } finally {
    loggingIn = false;
  }
}


function handleLoginSubmit(event: SubmitEvent) {
  event.preventDefault();
  void login();
}

function logout() {
  authToken = null;

  localStorage.removeItem(
    AUTH_TOKEN_KEY
  );

  loginUsername = '';
  loginPassword = '';

  newChat();
}

  function generateId(): string {

    if (

      typeof crypto !== 'undefined' &&

      typeof crypto.randomUUID === 'function'

    ) {

      return crypto.randomUUID();

    }



    return `id-${Date.now()}-${Math.random()

      .toString(16)

      .slice(2)}`;

  }



  function getActiveConversation(): Conversation | undefined {

    return conversations.find(

      (conversation) => conversation.id === activeConversationId

    );

  }

  function updateAnalysisContext(
    conversationId: string,
    data: ChatResponse
  ) {
    const conversation =
      conversations.find(
        (item) => item.id === conversationId
      );

    const previousContext =
      conversation?.context ?? null;

    const firstRow =
      Array.isArray(data.rows) &&
      data.rows.length > 0
        ? data.rows[0]
        : null;

    const entity =
      firstRow &&
      typeof firstRow.group_name === 'string'
        ? firstRow.group_name
        : previousContext?.entity ?? null;

    const nextContext: AnalysisContext = {
      metric:
        data.metric ??
        previousContext?.metric ??
        null,

      group_by:
        data.group_by ??
        previousContext?.group_by ??
        null,

      entity,

      year:
        data.year ??
        previousContext?.year ??
        null,

      country:
        data.country ??
        previousContext?.country ??
        null,

      product:
        data.product ??
        previousContext?.product ??
        null,

      segment:
        data.segment ??
        previousContext?.segment ??
        null
    };

    conversations = conversations.map((item) => {
      if (item.id !== conversationId) {
        return item;
      }

      return {
        ...item,
        context: nextContext
      };
    });

    saveConversations();
  }

  function getMessages(): Message[] {

    return getActiveConversation()?.messages ?? [];

  }



  function getTableColumns(rows: Row[]): string[] {

    const columns = new Set<string>();

    rows.forEach((row) => {
      Object.keys(row).forEach((key) => columns.add(key));
    });

    return Array.from(columns);

  }


  function titleCase(value: string): string {

    return value
      .replaceAll('_', ' ')
      .replace(/\b\w/g, (character) => character.toUpperCase());

  }


  function getColumnLabel(column: string, message: Message): string {

    if (column === 'group_name') {
      return titleCase(message.group_by ?? 'group');
    }

    if (column === 'value') {
      return titleCase(message.metric ?? 'value');
    }

    if (column === 'total_orders') {
      return 'Total Orders';
    }

    return titleCase(column);

  }
   
   function getChartType(
  message: Message
): 'bar' | 'line' | 'pie' | null {

  if (
    message.role !== 'assistant' ||
    message.source !== 'financials' ||
    !message.rows ||
    message.rows.length === 0 ||
    !message.group_by ||
    message.group_by === 'total'
  ) {
    return null;
  }

  if (
    message.group_by === 'month' ||
    message.group_by === 'year'
  ) {
    return 'line';
  }

  const firstRow = message.rows[0];

  if (
    firstRow.percentage !== undefined &&
    firstRow.percentage !== null
  ) {
    return 'pie';
  }

  return 'bar';
}

 function downloadRowsAsCsv(message: Message) {
  const rows = message.rows ?? [];

  if (rows.length === 0) {
    return;
  }

  const columns = getTableColumns(rows);

  const escapeCsvValue = (
    value: string | number | null | undefined
  ): string => {
    if (value === null || value === undefined) {
      return '';
    }

    const text = String(value);

    return `"${text.replaceAll('"', '""')}"`;
  };

  const header = columns
    .map((column) =>
      escapeCsvValue(
        getColumnLabel(column, message)
      )
    )
    .join(',');

  const body = rows.map((row) =>
    columns
      .map((column) =>
        escapeCsvValue(row[column])
      )
      .join(',')
  );

  const csv = [
    header,
    ...body
  ].join('\n');

  const blob = new Blob(
    [csv],
    {
      type: 'text/csv;charset=utf-8;'
    }
  );

  const url = URL.createObjectURL(blob);

  const link = document.createElement('a');

  const metric =
    message.metric ?? 'financial-data';

  const group =
    message.group_by ?? 'results';

  link.href = url;

  link.download =
    `${metric}-by-${group}.csv`;

  document.body.appendChild(link);

  link.click();

  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}

function downloadChartAsPng(message: Message) {
  const chartContainer = document.getElementById(
    `chart-${message.id}`
  );

  if (!chartContainer) {
    return;
  }

  const canvas =
    chartContainer.querySelector('canvas');

  if (!(canvas instanceof HTMLCanvasElement)) {
    return;
  }

  const imageUrl = canvas.toDataURL(
    'image/png',
    1.0
  );

  const link = document.createElement('a');

  const metric =
    message.metric ?? 'financial-data';

  const group =
    message.group_by ?? 'chart';

  link.href = imageUrl;

  link.download =
    `${metric}-by-${group}.png`;

  document.body.appendChild(link);

  link.click();

  document.body.removeChild(link);
}


 function getChartData(message: Message) {
  const rows = message.rows ?? [];

  const chartType = getChartType(message);

  if (chartType === 'pie') {
    const first = rows[0];

    const selected = Number(
      first.selected_value ?? 0
    );

    const total = Number(
      first.total_value ?? 0
    );

    const remainder = Math.max(
      total - selected,
      0
    );

    return {
      labels: [
        String(
          first.group_name ?? 'Selected'
        ),
        'Remaining'
      ],

      datasets: [
        {
          label: titleCase(
            message.metric ?? 'Value'
          ),

          data: [
            selected,
            remainder
          ]
        }
      ]
    };
  }

  return {
    labels: rows.map((row) =>
      String(
        row.group_name ??
        row.month_name ??
        row.year ??
        'Unknown'
      )
    ),

    datasets: [
      {
        label: titleCase(
          message.metric ?? 'Value'
        ),

        data: rows.map((row) =>
          Number(
            row.value ??
            row.total ??
            0
          )
        )
      }
    ]
  };
  }

function getChartOptions(message: Message) {
  const chartType = getChartType(message);

  const isMoney = isMoneyMetric(
    message.metric
  );

  return {
    responsive: true,

    maintainAspectRatio: false,

    interaction: {
      mode: 'index' as const,
      intersect: false
    },

    plugins: {
      legend: {
        display: chartType === 'pie',

        position: 'bottom' as const,

        labels: {
          boxWidth: 12,
          padding: 16
        }
      },

      title: {
        display: true,

        text:
          `${titleCase(message.metric ?? 'Value')} by ` +
          `${titleCase(message.group_by ?? 'Group')}`,

        font: {
          size: 16,
          weight: 'bold' as const
        },

        padding: {
          bottom: 18
        }
      },

      tooltip: {
        callbacks: {
          label: (context: any) => {
            const rawValue =
              typeof context.raw === 'number'
                ? context.raw
                : Number(context.raw ?? 0);

            const label =
              context.dataset?.label
                ? `${context.dataset.label}: `
                : '';

            if (isMoney) {
              return (
                label +
                new Intl.NumberFormat(
                  'en-US',
                  {
                    style: 'currency',
                    currency: 'USD',
                    maximumFractionDigits: 2
                  }
                ).format(rawValue)
              );
            }

            return (
              label +
              new Intl.NumberFormat(
                'en-US',
                {
                  maximumFractionDigits: 2
                }
              ).format(rawValue)
            );
          }
        }
      }
    },

    scales:
      chartType === 'pie'
        ? undefined
        : {
            x: {
              ticks: {
                maxRotation: 45,
                minRotation: 0
              },

              grid: {
                display: false
              }
            },

            y: {
              beginAtZero: true,

              ticks: {
                callback: (value: any) => {
                  const numericValue =
                    Number(value);

                  if (isMoney) {
                    return new Intl.NumberFormat(
                      'en-US',
                      {
                        notation: 'compact',
                        style: 'currency',
                        currency: 'USD',
                        maximumFractionDigits: 1
                      }
                    ).format(numericValue);
                  }

                  return new Intl.NumberFormat(
                    'en-US',
                    {
                      notation: 'compact',
                      maximumFractionDigits: 1
                    }
                  ).format(numericValue);
                }
              }
            }
          }
  };
}









  function isMoneyMetric(metric?: string): boolean {

    return [
      'sales',
      'profit',
      'cogs',
      'gross_sales',
      'discounts'
    ].includes(metric ?? '');

  }


  function formatCellValue(
    value: unknown,
    column?: string,
    message?: Message
  ): string {

    if (value === null || value === undefined) {
      return '—';
    }

    if (typeof value === 'number') {

      if (
        message?.source === 'financials' &&
        column === 'value'
      ) {

        if (isMoneyMetric(message.metric)) {
          return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 2
          }).format(value);
        }

        return new Intl.NumberFormat('en-US', {
          maximumFractionDigits: 2
        }).format(value);
      }

      return new Intl.NumberFormat('en-US', {
        maximumFractionDigits: 2
      }).format(value);

    }

    if (typeof value === 'string') {

      const numericValue = Number(value);

      if (
        message?.source === 'financials' &&
        column === 'value' &&
        value.trim() !== '' &&
        Number.isFinite(numericValue)
      ) {

        if (isMoneyMetric(message.metric)) {
          return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            maximumFractionDigits: 2
          }).format(numericValue);
        }

        return new Intl.NumberFormat('en-US', {
          maximumFractionDigits: 2
        }).format(numericValue);
      }

      return value;
    }

    if (typeof value === 'boolean') {
      return value ? 'true' : 'false';
    }

    try {
      return JSON.stringify(value);
    } catch {
      return String(value);
    }

  }


  function saveConversations() {

    if (typeof localStorage === 'undefined') return;



    try {

      if (conversations.length === 0) {

        localStorage.removeItem(STORAGE_KEY);

        localStorage.removeItem(ACTIVE_KEY);

        return;

      }



      localStorage.setItem(

        STORAGE_KEY,

        JSON.stringify(conversations)

      );



      if (activeConversationId) {

        localStorage.setItem(

          ACTIVE_KEY,

          activeConversationId

        );

      } else {

        localStorage.removeItem(ACTIVE_KEY);

      }

    } catch {

      console.warn('Could not save conversation history.');

    }

  }



  // ------------------------------------------

  // LOAD SAVED CONVERSATIONS

  // ------------------------------------------



  onMount(() => {

    if (typeof localStorage === 'undefined') {
      return;
    }

    const storedToken =
     localStorage.getItem(AUTH_TOKEN_KEY);

    if (storedToken) {
    authToken = storedToken;
    }

    try {

      const saved = localStorage.getItem(STORAGE_KEY);



      const active = localStorage.getItem(ACTIVE_KEY);



      if (saved) {

        const parsed = JSON.parse(saved);



        if (Array.isArray(parsed)) {

          conversations = parsed;

        }

      }



      if (

        active &&

        conversations.some((conversation) => conversation.id === active)

      ) {

        activeConversationId = active;

      }

    } catch {

      console.warn('Could not load saved conversations.');

    }

  });



  // ------------------------------------------

  // CREATE NEW CHAT

  // ------------------------------------------



  function newChat() {

    if (sending) return;



    activeConversationId = null;



    input = '';



    error = '';



    sidebarOpen = false;



    saveConversations();

  }



  // ------------------------------------------

  // SELECT EXISTING CHAT

  // ------------------------------------------



  function selectConversation(id: string) {

    if (sending) return;



    activeConversationId = id;



    error = '';



    sidebarOpen = false;



    saveConversations();



    scrollToBottom();

  }



  // ------------------------------------------

  // UPDATE CONVERSATION

  // ------------------------------------------



  function addMessage(

    conversationId: string,

    message: Message

  ) {

    conversations = conversations.map((conversation) => {

      if (conversation.id !== conversationId) {

        return conversation;

      }



      return {

        ...conversation,

        messages: [...conversation.messages, message]

      };

    });



    saveConversations();



    scrollToBottom();

  }



  // ------------------------------------------

  // SCROLL TO LATEST MESSAGE

  // ------------------------------------------



  function scrollToBottom() {

    setTimeout(() => {

      if (chatContainer) {

        chatContainer.scrollTop = chatContainer.scrollHeight;

      }

    }, 50);

  }



  // ------------------------------------------

  // SEND MESSAGE

  // ------------------------------------------

  async function sendMessage(
  event?: SubmitEvent
) {
  event?.preventDefault();

  const question = input.trim();

  if (!question || sending) {
    return;
  }

  error = '';

  let conversationId = activeConversationId;

  // ------------------------------------------
  // CREATE NEW CONVERSATION
  // ------------------------------------------

  if (!conversationId) {
    conversationId = generateId();

    const conversation: Conversation = {
      id: conversationId,

      title:
        question.length > 35
          ? question.substring(0, 35) + '...'
          : question,

      messages: [],

      context: null
    };

    conversations = [
      conversation,
      ...conversations
    ];

    activeConversationId = conversationId;
  }


  // ------------------------------------------
  // CAPTURE PREVIOUS STATE
  // BEFORE ADDING CURRENT QUESTION
  // ------------------------------------------

  const conversationBeforeQuestion =
    conversations.find(
      (conversation) =>
        conversation.id === conversationId
    );

  const previousMessages =
    conversationBeforeQuestion?.messages.slice(-8)
    ?? [];

  const analysisContext =
    conversationBeforeQuestion?.context
    ?? null;


  // ------------------------------------------
  // DISPLAY USER MESSAGE
  // ------------------------------------------

  addMessage(
    conversationId,
    {
      id: generateId(),
      role: 'user',
      text: question
    }
  );

  input = '';
  sending = true;

  scrollToBottom();


  // ------------------------------------------
  // SEND TO BACKEND
  // ------------------------------------------

  try {
    const response = await fetch(
      API_URL,
      {
        method: 'POST',

        headers: {
          'Content-Type': 'application/json',

          ...(authToken
            ? {
                Authorization:
                  `Bearer ${authToken}`
              }
            : {})
        },

        body: JSON.stringify({
          message: question,

          history:
            previousMessages.map(
              (message) => ({
                role: message.role,
                content: message.text
              })
            ),

          context: analysisContext
        })
      }
    );


    // ------------------------------------------
    // AUTH FAILURE
    // ------------------------------------------

    if (response.status === 401) {
      logout();

      throw new Error(
        'Your session has expired. Please log in again.'
      );
    }


    // ------------------------------------------
    // OTHER BACKEND ERROR
    // ------------------------------------------

    if (!response.ok) {
      let detail = '';

      try {
        const failure =
          await response.json();

        if (
          typeof failure.detail === 'string'
        ) {
          detail = failure.detail;
        }
      } catch {
        // Response may not contain JSON.
      }

      throw new Error(
        detail ||
        `Backend returned HTTP ${response.status}`
      );
    }


    // ------------------------------------------
    // READ RESPONSE
    // ------------------------------------------

    const data: ChatResponse =
      await response.json();

    if (
      typeof data.answer !== 'string'
    ) {
      throw new Error(
        'The backend returned an invalid response.'
      );
    }


    // ------------------------------------------
    // DISPLAY ASSISTANT MESSAGE
    // ------------------------------------------

    addMessage(
      conversationId,
      {
        id: generateId(),
        role: 'assistant',
        text: data.answer,

        rows:
          Array.isArray(data.rows)
            ? data.rows
            : [],

        group_by:
          data.group_by,

        source:
          data.source,

        metric:
          data.metric
      }
    );


    // ------------------------------------------
    // STORE ANALYSIS CONTEXT
    // ------------------------------------------

    updateAnalysisContext(
      conversationId,
      data
    );

  } catch (cause) {
    console.error(
      'Chat error:',
      cause
    );

    error =
      cause instanceof Error
        ? cause.message
        : 'Something went wrong. Please try again.';

  } finally {
    sending = false;

    saveConversations();

    scrollToBottom();
  }
}



  // ------------------------------------------

  // HANDLE ENTER KEY

  // ------------------------------------------



  function handleKeydown(event: KeyboardEvent) {

    if (

      event.key === 'Enter' &&

      !event.shiftKey &&

      !event.isComposing

    ) {

      event.preventDefault();



      void sendMessage();

    }

  }



  // ------------------------------------------

  // SUGGESTED QUESTION

  // ------------------------------------------



  function useSuggestion(question: string) {

    input = question;



    void sendMessage();

  }

</script>





<svelte:head>

  <title>Bundle Data Assistant</title>



  <meta

    name="description"

    content="AI-powered financial and order data assistant"

  />



  <meta

    name="viewport"

    content="width=device-width, initial-scale=1"

  />

</svelte:head>





{#if !authToken}

  <div class="login-page">

    <div class="login-card">

      <div class="login-brand">
        <div class="login-logo">
          B
        </div>

        <div>
          <h1>Bundle</h1>
          <p>Data Assistant</p>
        </div>
      </div>

      <div class="login-heading">
        <h2>Welcome back</h2>

        <p>
          Sign in to access financial analytics.
        </p>
      </div>

      <form
      class="login-form"
      onsubmit={handleLoginSubmit}
      >

        <label>
          Username

          <input
            type="text"
            bind:value={loginUsername}
            autocomplete="username"
            placeholder="Enter username"
            disabled={loggingIn}
          />
        </label>

        <label>
          Password

          <input
            type="password"
            bind:value={loginPassword}
            autocomplete="current-password"
            placeholder="Enter password"
            disabled={loggingIn}
          />
        </label>

        {#if loginError}
          <div class="login-error">
            {loginError}
          </div>
        {/if}

        <button
          class="login-button"
          type="submit"
          disabled={
            loggingIn ||
            !loginUsername.trim() ||
            !loginPassword
          }
        >
          {loggingIn
            ? 'Signing in...'
            : 'Sign in'}
        </button>

      </form>

    </div>

  </div>

{:else}

<div class="app">



  <!-- MOBILE SIDEBAR OVERLAY -->



  {#if sidebarOpen}

    <button

      class="overlay"

      aria-label="Close sidebar"

      onclick={() => sidebarOpen = false}

    ></button>

  {/if}





  <!-- SIDEBAR -->



  <aside class:open={sidebarOpen} class="sidebar">



    <div class="sidebar-header">



      <div class="brand">



        <div class="brand-icon">

          B

        </div>



        <div>

          <strong>Bundle</strong>

          <span>Data Assistant</span>

        </div>



      </div>



      <button

        class="new-chat"

        onclick={newChat}

        disabled={sending}

      >

        <span>＋</span>

        New Chat

      </button>



    </div>





    <div class="history">



      <p class="history-label">

        Your Conversations

      </p>



      {#each conversations as conversation (conversation.id)}



        <button

          class="history-item"

          class:active={activeConversationId === conversation.id}

          onclick={() => selectConversation(conversation.id)}

          disabled={sending}

        >



          <span class="history-icon">◇</span>



          <span class="history-title">

            {conversation.title}

          </span>



        </button>



      {/each}



    </div>





    <div class="sidebar-footer">

  <div class="sidebar-status">
    <div class="status-dot"></div>
    <span>Bundle Data Assistant</span>
  </div>

  <button
    class="logout-button"
    type="button"
    onclick={logout}
  >
    Log out
  </button>

</div>

  </aside>





  <!-- MAIN AREA -->



  <main class="main">



    <!-- TOP BAR -->



    <header class="topbar">



      <div class="topbar-left">



        <button

          class="menu-button"

          aria-label="Open sidebar"

          onclick={() => sidebarOpen = !sidebarOpen}

        >

          ☰

        </button>



        <div class="topbar-title">

          Bundle Data Assistant

        </div>



      </div>



      <div class="topbar-badge">

        AI Powered

      </div>



    </header>





    <!-- CHAT AREA -->



    <div

      class="chat-area"

      bind:this={chatContainer}

    >



      {#if getMessages().length === 0}



        <!-- WELCOME SCREEN -->



        <div class="welcome">



          <div class="welcome-logo">

            B

          </div>



          <h1>

            Bundle Data Assistant

          </h1>



          <p>

            Ask questions about your financial data.

            I’ll analyze PostgreSQL and return data-backed answers.

          </p>





          <div class="suggestions">



            {#each suggestions as suggestion}



              <button

                class="suggestion"

                onclick={() => useSuggestion(suggestion)}

                disabled={sending}

              >



                <span class="suggestion-icon">

                  ↗

                </span>



                {suggestion}



              </button>



            {/each}



          </div>



        </div>



      {:else}



        <!-- CONVERSATION -->



        <div class="conversation">



          {#each getMessages() as message (message.id)}



            <div

              class="message-row"

              class:user-row={message.role === 'user'}

            >



              {#if message.role === 'assistant'}



                <div class="assistant-avatar">

                  B

                </div>



              {/if}





              <div

                class="message-content"

                class:user-message={message.role === 'user'}

                class:assistant-message={message.role === 'assistant'}

              >



                {#if message.role === 'assistant'}



                  <div class="message-name">

                    Bundle Assistant

                  </div>



                {/if}





                <div class="message-text">

                  {message.text}

                </div>





                <!-- DATABASE RESULTS -->



                {#if message.rows && message.rows.length > 0}


                <!-- RANKING CONTRIBUTION VISUALIZATION -->

{#if message.rows.some(
  (row) => typeof row.contribution_percent === 'number'
)}
  <div class="contribution-panel">
    <div class="contribution-heading">
      <h3>Contribution Breakdown</h3>
      <span>Percentage of selected total</span>
    </div>

    {#each message.rows.filter(
      (row) => typeof row.contribution_percent === 'number'
    ) as row, index}
      {@const percentage = Number(row.contribution_percent)}
      {@const barWidth = Math.max(
        0,
        Math.min(Math.abs(percentage), 100)
      )}

      <div class="contribution-item">
        <div class="contribution-details">
          <div class="contribution-name">
            <span class="rank-number">
              #{row.rank ?? index + 1}
            </span>

            <span>{String(row.group_name ?? 'Unknown')}</span>
          </div>

          <strong>
            {percentage.toFixed(2)}%
          </strong>
        </div>

        <div
          class="contribution-track"
          role="progressbar"
          aria-label={`Absolute contribution magnitude for ${String(row.group_name ?? 'Unknown')}`}
          aria-valuemin="0"
          aria-valuemax="100"
          aria-valuenow={barWidth}
        >
          <div
            class="contribution-fill"
            class:negative={percentage < 0}
            style:width={`${barWidth}%`}
          ></div>
        </div>
      </div>
    {/each}

    <p class="contribution-note">
      Bars show absolute contribution magnitude, capped at
      100% for display. Signed percentages above are the
      actual calculated values.
    </p>
  </div>
{/if}

  {#if getChartType(message)}
    <div class="chart-wrapper"
    id={`chart-${message.id}`}
    >
      {#if getChartType(message) === 'line'}

  <Line
    data={getChartData(message)}
    options={getChartOptions(message)}
  />

{:else if getChartType(message) === 'pie'}

  <Pie
    data={getChartData(message)}
    options={getChartOptions(message)}
  />

{:else}

  <Bar
    data={getChartData(message)}
    options={getChartOptions(message)}
  />

{/if}

    </div>
  {/if}

  <div class="table-wrapper">



                    <table>



                      <thead>



                        <tr>



                          {#each getTableColumns(message.rows) as column}



                            <th>

                              {getColumnLabel(column, message)}

                            </th>



                          {/each}



                        </tr>



                      </thead>





                      <tbody>



                        {#each message.rows as row}



                          <tr>



                            {#each getTableColumns(message.rows ?? []) as column}



                              <td>

                                {formatCellValue(row[column], column, message)}

                              </td>



                            {/each}



                          </tr>



                        {/each}



                      </tbody>



                    </table>



                  </div>

          <div class="result-actions">

  <button
    class="download-button"
    type="button"
    onclick={() =>
      downloadRowsAsCsv(message)
    }
  >
    ↓ Download CSV
  </button>

  {#if getChartType(message)}

    <button
      class="download-button"
      type="button"
      onclick={() =>
        downloadChartAsPng(message)
      }
    >
      ↓ Download Chart
    </button>

  {/if}

</div>



                {/if}



              </div>



            </div>



          {/each}





          <!-- LOADING INDICATOR -->



          {#if sending}



            <div class="message-row">



              <div class="assistant-avatar">

                B

              </div>



              <div class="loading">



                <span></span>

                <span></span>

                <span></span>



              </div>



            </div>



          {/if}



        </div>



      {/if}



    </div>





    <!-- ERROR MESSAGE -->



    {#if error}



      <div class="error-message" role="alert">



        {error}



      </div>



    {/if}





    <!-- INPUT AREA -->



    <div class="input-section">



      <form

        class="input-box"

        onsubmit={sendMessage}

      >



        <textarea

          bind:value={input}

          onkeydown={handleKeydown}

          placeholder="Ask about sales, profit, products, countries, segments..."

          aria-label="Your message"

          rows="1"

          disabled={sending}

        ></textarea>





        <button

          class="send-button"

          type="submit"

          disabled={sending || !input.trim()}

          aria-label="Send message"

        >



          {sending ? '…' : '↑'}



        </button>



      </form>





      <p class="input-hint">



        Bundle Data Assistant · Powered by Groq & PostgreSQL



      </p>



    </div>



  </main>



 </div>

{/if}




<style>

  :global(*) {

    box-sizing: border-box;

  }



  :global(html) {

    height: 100%;

    background: #ffffff;

  }



  :global(body) {

    margin: 0;

    min-height: 100%;

    font-family:

      Inter,

      -apple-system,

      BlinkMacSystemFont,

      'Segoe UI',

      sans-serif;

    color: #202123;

  }



  :global(button),

  :global(textarea) {

    font: inherit;

  }

  .result-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;

  gap: 10px;

  margin-top: 12px;

  flex-wrap: wrap;
}

.download-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;

  min-height: 38px;

  padding: 8px 14px;

  border: 1px solid #d1d5db;
  border-radius: 10px;

  background: #ffffff;

  color: #111827;

  font-size: 13px;
  font-weight: 600;

  cursor: pointer;

  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.download-button:hover {
  background: #f3f4f6;
  border-color: #9ca3af;
}

.download-button:active {
  transform: translateY(1px);
}

@media (max-width: 480px) {
  .result-actions {
    flex-direction: column;
    justify-content: stretch;
  }

  .download-button {
    width: 100%;
  }
}





  /* APP */



  .app {

    display: flex;

    height: 100dvh;

    min-height: 0;

    overflow: hidden;

    background: white;

  }





  /* SIDEBAR */



  .sidebar {

    width: 260px;

    flex-shrink: 0;

    background: #f7f7f8;

    border-right: 1px solid #e9e9eb;

    display: flex;

    flex-direction: column;

    z-index: 20;

  }



  .sidebar-header {

    padding: 20px 14px;

  }



  .brand {

    display: flex;

    align-items: center;

    gap: 12px;

    padding: 4px 6px 24px;

  }



  .brand-icon {

    width: 36px;

    height: 36px;

    background: #111827;

    color: white;

    border-radius: 11px;

    display: flex;

    align-items: center;

    justify-content: center;

    font-weight: 700;

    font-size: 19px;

  }



  .brand strong {

    display: block;

    font-size: 15px;

  }



  .brand span {

    display: block;

    color: #777;

    font-size: 12px;

    margin-top: 3px;

  }



  .new-chat {

    width: 100%;

    border: 1px solid #dedee2;

    background: white;

    padding: 12px;

    border-radius: 10px;

    cursor: pointer;

    text-align: left;

    font-weight: 500;

    display: flex;

    align-items: center;

    gap: 10px;

    color: #202123;

  }



  .new-chat span {

    font-size: 21px;

  }



  .new-chat:hover {

    background: #eeeeef;

  }



  .new-chat:disabled {

    opacity: 0.5;

    cursor: not-allowed;

  }

  /* Login Page */

  .login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: #f7f7f8;
}

.login-card {
  width: 100%;
  max-width: 420px;
  padding: 32px;
  border: 1px solid #e5e7eb;
  border-radius: 18px;
  background: #ffffff;
  box-shadow:
    0 10px 30px
    rgba(0, 0, 0, 0.06);
}

.login-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}

.login-logo {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: #111827;
  color: #ffffff;
  font-weight: 700;
  font-size: 20px;
}

.login-heading {
  margin-bottom: 24px;
}

.login-heading h2 {
  margin: 0 0 6px;
}

.login-heading p {
  margin: 0;
  color: #6b7280;
  font-size: 14px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.login-form label {
  display: flex;
  flex-direction: column;
  gap: 7px;
  font-size: 13px;
  font-weight: 600;
}

.login-form input {
  width: 100%;
  padding: 11px 12px;
  border: 1px solid #d1d5db;
  border-radius: 10px;
  font-size: 14px;
  outline: none;
}

.login-button {
  min-height: 44px;
  border: none;
  border-radius: 10px;
  background: #111827;
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.login-button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.login-error {
  padding: 10px 12px;
  border-radius: 8px;
  background: #fef2f2;
  color: #b91c1c;
  font-size: 13px;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sidebar-status {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logout-button {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
}

.logout-button:hover {
  background: #f3f4f6;
}



/* CONTRIBUTION BREAKDOWN */

.contribution-panel {
  margin-top: 20px;
  padding: 20px;
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
}

.contribution-heading {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 22px;
  flex-wrap: wrap;
}

.contribution-heading h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 650;
  color: #111827;
}

.contribution-heading span {
  color: #6b7280;
  font-size: 12px;
}

.contribution-item {
  margin-bottom: 18px;
}

.contribution-details {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  font-size: 13px;
}

.contribution-name {
  display: flex;
  align-items: center;
  gap: 9px;
  min-width: 0;
  overflow-wrap: anywhere;
}

.rank-number {
  color: #64748b;
  font-weight: 600;
  flex-shrink: 0;
}

.contribution-details strong {
  font-size: 13px;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

.contribution-track {
  height: 11px;
  background: #edf2f7;
  border-radius: 999px;
  overflow: hidden;
}

.contribution-fill {
  height: 100%;
  background: linear-gradient(
    90deg,
    #2563eb,
    #60a5fa
  );
  border-radius: 999px;
  transition: width 350ms ease;
}

.contribution-fill.negative {
  background: #ef4444;
}

.contribution-note {
  font-size: 11px;
  color: #64748b;
  line-height: 1.5;
  margin: 12px 0 0;
}

@media (max-width: 600px) {
  .contribution-panel {
    padding: 14px;
  }

  .contribution-details {
    font-size: 12px;
  }
}

  /* HISTORY */



  .history {

    flex: 1;

    overflow-y: auto;

    padding: 10px;

  }



  .history-label {

    font-size: 11px;

    color: #858585;

    text-transform: uppercase;

    letter-spacing: 0.7px;

    padding: 0 12px;

    margin: 10px 0 14px;

  }



  .history-item {

    display: flex;

    align-items: center;

    width: 100%;

    border: none;

    background: transparent;

    border-radius: 9px;

    padding: 12px;

    margin-bottom: 4px;

    text-align: left;

    cursor: pointer;

    gap: 10px;

    color: #444;

    font-size: 13px;

  }



  .history-item:hover {

    background: #ebebed;

  }



  .history-item.active {

    background: #e5e5e8;

    color: #111;

    font-weight: 500;

  }



  .history-item:disabled {

    cursor: not-allowed;

  }



  .history-icon {

    font-size: 18px;

    color: #777;

  }



  .history-title {

    overflow: hidden;

    white-space: nowrap;

    text-overflow: ellipsis;

  }





  /* SIDEBAR FOOTER */



  .sidebar-footer {

    display: flex;

    align-items: center;

    gap: 8px;

    border-top: 1px solid #e5e5e5;

    padding: 18px;

    font-size: 12px;

    color: #777;

  }



  .status-dot {

    width: 8px;

    height: 8px;

    background: #10a37f;

    border-radius: 50%;

  }





  /* MAIN */



  .main {

    display: flex;

    flex-direction: column;

    flex: 1;

    min-width: 0;

    min-height: 0;

    background: white;

  }





  /* TOP BAR */



  .topbar {

    height: 64px;

    flex-shrink: 0;

    display: flex;

    align-items: center;

    justify-content: space-between;

    padding: 0 28px;

    border-bottom: 1px solid #f0f0f0;

  }



  .topbar-left {

    display: flex;

    align-items: center;

    gap: 14px;

  }



  .topbar-title {

    font-weight: 600;

    font-size: 16px;

  }



  .topbar-badge {

    font-size: 12px;

    background: #e9f8f2;

    color: #16815f;

    padding: 7px 12px;

    border-radius: 30px;

    font-weight: 500;

  }



  .menu-button {

    display: none;

    border: none;

    background: transparent;

    font-size: 23px;

    cursor: pointer;

    color: #333;

  }





  /* CHAT */



  .chat-area {

    flex: 1;

    min-height: 0;

    overflow-y: auto;

    overflow-x: hidden;

    padding: 24px;

  }



  .conversation {

    max-width: 850px;

    margin: 0 auto;

    padding: 18px 0 50px;

  }



  .message-row {

    display: flex;

    align-items: flex-start;

    gap: 15px;

    margin-bottom: 30px;

  }



  .user-row {

    justify-content: flex-end;

  }



  .assistant-avatar {

    width: 32px;

    height: 32px;

    flex-shrink: 0;

    border-radius: 10px;

    background: #111827;

    color: white;

    display: flex;

    align-items: center;

    justify-content: center;

    font-size: 16px;

    font-weight: 700;

  }



  .message-content {

    min-width: 0;

    max-width: 85%;

  }



  .user-message {

    background: #f2f2f3;

    border-radius: 18px;

    padding: 12px 18px;

  }



  .assistant-message {

    flex: 1;

    padding-top: 4px;

  }



  .message-name {

    font-weight: 600;

    font-size: 13px;

    margin-bottom: 9px;

  }



  .message-text {

    font-size: 14px;

    line-height: 1.7;

    white-space: pre-wrap;

    overflow-wrap: anywhere;

  }




  /* TABLES */



  .table-wrapper {

    margin-top: 18px;

    overflow-x: auto;

    border: 1px solid #e5e7eb;

    border-radius: 10px;

    max-width: 100%;

  }

  .chart-wrapper {
  width: 100%;
  height: 340px;

  margin-top: 18px;
  margin-bottom: 18px;

  padding: 18px;

  border: 1px solid #e5e7eb;

  border-radius: 16px;

  background: #ffffff;

  overflow: hidden;
}

@media (max-width: 768px) {
  .chart-wrapper {
    height: 280px;

    padding: 12px;

    margin-top: 14px;
    margin-bottom: 14px;

    border-radius: 12px;
  }
}

@media (max-width: 480px) {
  .chart-wrapper {
    height: 240px;

    padding: 8px;
  }
}



  table {

    width: 100%;

    border-collapse: collapse;

    font-size: 13px;

  }



  th {

    background: #f8f9fb;

    color: #555;

    text-align: left;

    font-weight: 600;

    text-transform: capitalize;

    white-space: nowrap;

  }



  th,

  td {

    padding: 13px 16px;

    border-bottom: 1px solid #eeeeef;

  }



  tbody tr:last-child td {

    border-bottom: none;

  }



  tbody tr:hover {

    background: #fafafa;

  }



  /* WELCOME */



  .welcome {

    max-width: 720px;

    min-height: 100%;

    margin: auto;

    display: flex;

    flex-direction: column;

    justify-content: center;

    align-items: center;

    text-align: center;

    padding: 30px 0;

  }



  .welcome-logo {

    width: 60px;

    height: 60px;

    border-radius: 18px;

    display: flex;

    align-items: center;

    justify-content: center;

    background: #111827;

    color: white;

    font-size: 30px;

    font-weight: 700;

    margin-bottom: 24px;

  }



  .welcome h1 {

    font-size: clamp(23px, 4vw, 32px);

    letter-spacing: -0.8px;

    margin: 0;

  }



  .welcome p {

    color: #777;

    font-size: 14px;

    line-height: 1.7;

    max-width: 430px;

    margin: 16px 0 32px;

  }



  .suggestions {

    display: grid;

    grid-template-columns: repeat(2, minmax(0, 1fr));

    gap: 12px;

    width: 100%;

    max-width: 560px;

  }



  .suggestion {

    border: 1px solid #e5e5e5;

    border-radius: 12px;

    background: white;

    padding: 17px;

    text-align: left;

    cursor: pointer;

    font-size: 13px;

    line-height: 1.5;

    color: #333;

  }



  .suggestion:hover {

    background: #f8f8f8;

    border-color: #cccccc;

  }



  .suggestion-icon {

    display: block;

    font-size: 18px;

    color: #10a37f;

    margin-bottom: 12px;

  }




  /* LOADING */



  .loading {

    display: flex;

    align-items: center;

    gap: 5px;

    padding-top: 12px;

  }



  .loading span {

    width: 7px;

    height: 7px;

    background: #9ca3af;

    border-radius: 50%;

    animation: pulse 1.2s infinite;

  }



  .loading span:nth-child(2) {

    animation-delay: 0.2s;

  }



  .loading span:nth-child(3) {

    animation-delay: 0.4s;

  }



  @keyframes pulse {

    0%, 60%, 100% {

      opacity: 0.3;

      transform: translateY(0);

    }



    30% {

      opacity: 1;

      transform: translateY(-4px);

    }

  }





  /* INPUT */



  .input-section {

    width: 100%;

    padding: 16px 24px 12px;

    background: white;

  }



  .input-box {

    max-width: 850px;

    margin: 0 auto;

    border: 1px solid #dedee2;

    border-radius: 18px;

    display: flex;

    align-items: flex-end;

    padding: 12px;

    gap: 10px;

    background: white;

    box-shadow: 0 3px 15px rgba(0, 0, 0, 0.035);

  }



  .input-box:focus-within {

    border-color: #aaaaaf;

  }



  textarea {

    flex: 1;

    min-width: 0;

    border: none;

    outline: none;

    resize: none;

    background: transparent;

    padding: 10px;

    font-size: 14px;

    line-height: 1.5;

    max-height: 160px;

  }



  .send-button {

    width: 36px;

    height: 36px;

    flex-shrink: 0;

    background: #111827;

    color: white;

    border: none;

    border-radius: 11px;

    font-size: 23px;

    cursor: pointer;

  }



  .send-button:hover {

    background: #374151;

  }



  .send-button:disabled {

    opacity: 0.35;

    cursor: not-allowed;

  }



  .input-hint {

    text-align: center;

    font-size: 11px;

    color: #999;

    margin: 11px 0 0;

  }



  .error-message {

    width: min(850px, calc(100% - 48px));

    margin: 0 auto;

    padding: 12px;

    background: #fff0f0;

    color: #b42318;

    border-radius: 8px;

    font-size: 13px;

  }





  /* MOBILE */



  .overlay {

    display: none;

  }



  @media (max-width: 768px) {



    .sidebar {

      position: fixed;

      top: 0;

      left: 0;

      height: 100dvh;

      width: min(280px, 85vw);

      transform: translateX(-100%);

      transition: transform 0.25s ease;

    }



    .sidebar.open {

      transform: translateX(0);

    }



    .overlay {

      display: block;

      position: fixed;

      inset: 0;

      background: rgba(0, 0, 0, 0.4);

      border: none;

      z-index: 15;

    }



    .menu-button {

      display: block;

    }



    .topbar {

      height: 58px;

      padding: 0 16px;

    }



    .topbar-title {

      font-size: 14px;

    }



    .topbar-badge {

      font-size: 10px;

      padding: 6px 9px;

    }



    .chat-area {

      padding: 14px;

    }



    .conversation {

      padding-top: 10px;

    }



    .message-row {

      gap: 10px;

      margin-bottom: 24px;

    }



    .message-content {

      max-width: 88%;

    }



    .assistant-avatar {

      width: 27px;

      height: 27px;

      border-radius: 8px;

    }



    .message-text {

      font-size: 13px;

    }



    .welcome {

      padding: 20px 0;

    }



    .welcome h1 {

      font-size: 24px;

    }



    .suggestions {

      grid-template-columns: 1fr;

    }



    .suggestion {

      padding: 12px 15px;

    }



    .suggestion-icon {

      display: inline;

      margin-right: 10px;

    }



    .input-section {

      padding: 10px 12px;

      padding-bottom: max(10px, env(safe-area-inset-bottom));

    }



    .input-box {

      border-radius: 15px;

      padding: 8px;

    }



    .input-hint {

      font-size: 9px;

    }



    th,

    td {

      padding: 10px;

      font-size: 12px;

    }



  }



</style>