
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
  // Safe assistant text formatting
  // ------------------------------------------

  function renderAssistantText(value: string): string {
    // Escape HTML first so model/database text cannot inject markup.
    const escaped = value
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');

    // Support the small Markdown subset Bundle actually emits:
    // **bold**, *italic*, `inline code`, and line breaks.
    return escaped
      .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
      .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, '<em>$1</em>')
      .replace(/`([^`\n]+)`/g, '<code>$1</code>')
      .replace(/\r?\n/g, '<br />');
  }


  // ------------------------------------------
  // Authentication - Login page
  //-------------------------------------------

  let loginUsername = $state('');
  let loginPassword = $state('');
  let revealPassword = $state(false);
  let authToken = $state<string | null>(null);
  let loginError = $state('');
  let loggingIn = $state(false);

  type UserRole = 'admin' | 'analyst' | 'viewer';

  type CurrentUser = {
    id?: number;
    username: string;
    role: UserRole;
  };

  let currentUser = $state<CurrentUser | null>(null);
  let authProfileLoading = $state(false);


  type BusinessMeasure = {
    column_name: string;
    total: number | null;
    average: number | null;
    minimum: number | null;
    maximum: number | null;
    non_null_rows: number;
  };

  type BusinessCategoryValue = {
    name: string;
    total: number | null;
    row_count: number;
  };

  type BusinessCategoryBreakdown = {
    category_column: string;
    measure_column: string;
    values: BusinessCategoryValue[];
  };

  type BusinessProfile = {
    dataset_name: string;
    analytics_table: string;
    total_rows: number;
    date_ranges: Record<
      string,
      {
        minimum: string | null;
        maximum: string | null;
      }
    >;
    measures: BusinessMeasure[];
    category_breakdowns: BusinessCategoryBreakdown[];
    primary_measure: string | null;
    quick_summary: string;
    suggested_questions: string[];
    generated_at: string;
  };

  let businessProfile = $state<BusinessProfile | null>(null);
  let businessProfileLoading = $state(false);
  let businessProfileError = $state('');
  let businessProfileExpanded = $state(false);

  type WorkspaceView = 'chat' | 'admin' | 'audit';

  type ManagedUser = {
    id: number;
    username: string;
    role: UserRole;
    is_active: boolean;
    created_at: string;
    updated_at: string;
    last_login_at: string | null;
  };

  let workspaceView = $state<WorkspaceView>('chat');
  let managedUsers = $state<ManagedUser[]>([]);
  let adminUsersLoading = $state(false);
  let adminActionLoading = $state(false);
  let adminError = $state('');
  let adminNotice = $state('');

  let newUserUsername = $state('');
  let newUserPassword = $state('');
  let newUserRole = $state<UserRole>('analyst');

  let resetPasswordUserId = $state<number | null>(null);
  let resetPasswordValue = $state('');

  type AuditLogItem = {
    username: string;
    question: string;
    tool_name: string | null;
    status: string;
    execution_time_ms: number | null;
    error_message: string | null;
    created_at: string;
  };

  let auditLogs = $state<AuditLogItem[]>([]);
  let auditLoading = $state(false);
  let auditError = $state('');
  let auditUsernameFilter = $state('');
  let auditStatusFilter = $state('');
  let auditToolFilter = $state('');

  const AUTH_TOKEN_KEY = 'bundle-data-assistant-token';

  // ------------------------------------------

  // TYPES

  // ------------------------------------------



  type Row = Record<string, string | number | null>;

  

  type RAGCitation = {
    index: number;
    document_id: string;
    title?: string | null;
    document_type?: string | null;
    access_level?: string | null;
    similarity?: number | null;
  };


  type Message = {

    id: string;

    role: 'user' | 'assistant';

    text: string;

    rows?: Row[];

    group_by?: string;

    source?: 'orders' | 'financials' | 'active_dataset' | 'rag_required' | 'rag' | 'hybrid' | 'forecast' | 'scenario';

    metric?: string;

    question?: string;

    deepAnswer?: string;

    deepEvidence?: Record<string, unknown>;

    deepLoading?: boolean;

    deepError?: string;

    citations?: RAGCitation[];

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

    source?: 'orders' | 'financials' | 'active_dataset' | 'rag_required' | 'rag' | 'hybrid' | 'forecast' | 'scenario';

    metric?: string;

    answer_mode?: 'summary' | 'detailed';

    evidence?: Record<string, unknown>;

    citations?: RAGCitation[];

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

  // UI-only enhancements. No changes to API or authorization logic.
  let historyQuery = $state('');
  let copyNotice = $state<string | null>(null);
  let exportNotice = $state('');


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



  function isUserRole(value: unknown): value is UserRole {
    return value === 'admin' || value === 'analyst' || value === 'viewer';
  }

  function canUseChat(): boolean {
    return currentUser?.role === 'admin' || currentUser?.role === 'analyst';
  }

  function roleLabel(): string {
    if (!currentUser) {
      return authProfileLoading ? 'VERIFYING' : 'SIGNED IN';
    }

    return currentUser.role.toUpperCase();
  }

  function userInitial(): string {
    return currentUser?.username?.trim().charAt(0).toUpperCase() || 'B';
  }


  function formatProfileNumber(value: number | null): string {
    if (value === null || !Number.isFinite(value)) {
      return '—';
    }

    const absolute = Math.abs(value);

    if (absolute >= 1_000_000_000) {
      return `${(value / 1_000_000_000).toFixed(2)}B`;
    }

    if (absolute >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(2)}M`;
    }

    if (absolute >= 1_000) {
      return `${(value / 1_000).toFixed(2)}K`;
    }

    return new Intl.NumberFormat(undefined, {
      maximumFractionDigits: 2
    }).format(value);
  }

  function profileDateRange(): string {
    if (!businessProfile) {
      return 'No date range';
    }

    const firstRange =
      Object.values(businessProfile.date_ranges ?? {})[0];

    if (!firstRange?.minimum || !firstRange?.maximum) {
      return 'Date range unavailable';
    }

    return `${firstRange.minimum} → ${firstRange.maximum}`;
  }

  async function loadBusinessProfile(
    tokenOverride?: string
  ) {
    const token = tokenOverride ?? authToken;

    if (!token) {
      businessProfile = null;
      businessProfileError = '';
      return;
    }

    businessProfileLoading = true;
    businessProfileError = '';

    try {
      const response = await fetch(
        '/api/datasets/active/profile',
        {
          headers: {
            Authorization: `Bearer ${token}`
          }
        }
      );

      if (response.status === 401) {
        logout();
        throw new Error(
          'Your session has expired. Please log in again.'
        );
      }

      if (!response.ok) {
        let detail =
          `Profile request failed with HTTP ${response.status}`;

        try {
          const failure = await response.json();

          if (typeof failure.detail === 'string') {
            detail = failure.detail;
          }
        } catch {
          // Response may not contain JSON.
        }

        throw new Error(detail);
      }

      const data = await response.json();

      if (
        typeof data.dataset_name !== 'string' ||
        typeof data.quick_summary !== 'string' ||
        typeof data.total_rows !== 'number'
      ) {
        throw new Error(
          'The backend returned an invalid dataset profile.'
        );
      }

      businessProfile = data as BusinessProfile;
    } catch (cause) {
      businessProfile = null;

      businessProfileError =
        cause instanceof Error
          ? cause.message
          : 'Unable to load the active dataset profile.';
    } finally {
      businessProfileLoading = false;
    }
  }

  async function restoreSession(token: string) {
    authProfileLoading = true;

    try {
      const response = await fetch('/api/me', {
        headers: {
          Authorization: `Bearer ${token}`
        }
      });

      if (!response.ok) {
        throw new Error('Session unavailable.');
      }

      const data = await response.json();

      if (
        typeof data.username !== 'string' ||
        !isUserRole(data.role)
      ) {
        throw new Error('Invalid account profile.');
      }

      currentUser = {
        id: typeof data.id === 'number' ? data.id : undefined,
        username: data.username,
        role: data.role
      };

      void loadBusinessProfile(token);
    } catch {
      authToken = null;
      currentUser = null;
      localStorage.removeItem(AUTH_TOKEN_KEY);
    } finally {
      authProfileLoading = false;
    }
  }

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

    if (
      typeof data.username !== 'string' ||
      !isUserRole(data.role)
    ) {
      throw new Error(
        'Login response did not include a valid user profile.'
      );
    }

    authToken = data.access_token;

    currentUser = {
      username: data.username,
      role: data.role
    };

    void loadBusinessProfile(data.access_token);

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
  currentUser = null;
  authProfileLoading = false;
  workspaceView = 'chat';
  managedUsers = [];
  auditLogs = [];
  auditError = '';
  adminError = '';
  adminNotice = '';
  businessProfile = null;
  businessProfileLoading = false;
  businessProfileError = '';
  businessProfileExpanded = false;

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
          ],
          backgroundColor: ['#e5e7eb', '#3b3b3b'],
          borderColor: ['#fafafa', '#3b3b3b'],
          borderWidth: 1,
          hoverOffset: 8
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
        ),
        backgroundColor: chartType === 'line'
          ? 'rgba(180, 190, 210, 0.10)'
          : rows.map((_, index) =>
              ['#fafafa', '#a3a3a3', '#737373', '#525252', '#d4d4d4'][index % 5]
            ),
        borderColor: chartType === 'line' ? '#f5f5f5' : '#909090',
        borderWidth: chartType === 'line' ? 3 : 1,
        borderRadius: chartType === 'bar' ? 8 : 0,
        borderSkipped: false,
        fill: chartType === 'line',
        tension: 0.35,
        pointRadius: chartType === 'line' ? 4 : 0,
        pointHoverRadius: 6,
        pointBackgroundColor: '#f5f5f5',
        maxBarThickness: 76
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
          padding: 16,
          color: '#c6c6c6' 
        }
      },

      title: {
        display: true,

        text:
          `${titleCase(message.metric ?? 'Value')} by ` +
          `${titleCase(message.group_by ?? 'Group')}`,

        color: '#eaeaea',
        font: {
          size: 16,
          weight: 'bold' as const
        },

        padding: {
          bottom: 18
        }
      },

      tooltip: {
        backgroundColor: '#171717',
        borderColor: '#383838',
        borderWidth: 1,
        titleColor: '#f5f5f5',
        bodyColor: '#bdbdbd',
        padding: 12,
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
                color: '#a3a3a3',
                maxRotation: 35,
                minRotation: 0
              },

              grid: {
                display: false
              },
              border: {display: false}
            },

            y: {
              beginAtZero: true,

              grid: {color: 'rgba(255, 255, 255, 0.075)'},
              border: {display: false},
              ticks: {
                color: '#a3a3a3',
                padding: 12,
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
      void restoreSession(storedToken);
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




  function updateMessage(
    conversationId: string,
    messageId: string,
    patch: Partial<Message>
  ) {
    conversations = conversations.map(
      (conversation) => {
        if (
          conversation.id !== conversationId
        ) {
          return conversation;
        }

        return {
          ...conversation,
          messages:
            conversation.messages.map(
              (message) =>
                message.id === messageId
                  ? {
                      ...message,
                      ...patch
                    }
                  : message
            )
        };
      }
    );

    saveConversations();
  }

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



  async function requestDeepAnalysis(
    message: Message
  ) {
    if (
      message.role !== 'assistant' ||
      !message.question ||
      !authToken ||
      message.deepLoading
    ) {
      return;
    }

    const conversationId =
      activeConversationId;

    if (!conversationId) {
      return;
    }

    updateMessage(
      conversationId,
      message.id,
      {
        deepLoading: true,
        deepError: ''
      }
    );

    try {
      const response = await fetch(
        API_URL,
        {
          method: 'POST',

          headers: {
            'Content-Type': 'application/json',
            Authorization:
              `Bearer ${authToken}`
          },

          body: JSON.stringify({
            message: message.question,
            history: [],
            context: null,
            answer_mode: 'detailed'
          })
        }
      );

      if (response.status === 401) {
        logout();

        throw new Error(
          'Your session has expired. Please log in again.'
        );
      }

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

      const data: ChatResponse =
        await response.json();

      if (
        typeof data.answer !== 'string'
      ) {
        throw new Error(
          'The backend returned an invalid detailed response.'
        );
      }

      updateMessage(
        conversationId,
        message.id,
        {
          deepAnswer: data.answer,
          deepEvidence:
            data.evidence ?? {},
          citations:
            data.citations ?? message.citations ?? [],
          deepLoading: false,
          deepError: ''
        }
      );

      setTimeout(
        scrollToBottom,
        0
      );
    } catch (cause) {
      console.error(
        'Deep analysis error:',
        cause
      );

      updateMessage(
        conversationId,
        message.id,
        {
          deepLoading: false,
          deepError:
            cause instanceof Error
              ? cause.message
              : 'Unable to load detailed analysis.'
        }
      );
    }
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

  if (!canUseChat()) {
    error = currentUser?.role === 'viewer'
      ? 'Viewer accounts have read-only workspace access. AI chat is available to Analysts and Admins.'
      : 'Your account permissions are still being verified.';
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

          context: analysisContext,
          answer_mode: 'summary'
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
          data.metric,

        question,

        citations:
          data.citations ?? []
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


  async function adminRequest(
    path: string,
    options: RequestInit = {}
  ) {
    if (!authToken) {
      throw new Error('Authentication required.');
    }

    const response = await fetch(path, {
      ...options,
      headers: {
        ...(options.body
          ? { 'Content-Type': 'application/json' }
          : {}),
        Authorization: `Bearer ${authToken}`,
        ...(options.headers ?? {})
      }
    });

    if (response.status === 401) {
      logout();
      throw new Error('Your session has expired. Please log in again.');
    }

    if (!response.ok) {
      let detail = `Request failed with HTTP ${response.status}`;

      try {
        const failure = await response.json();
        if (typeof failure.detail === 'string') {
          detail = failure.detail;
        }
      } catch {
        // Response may not contain JSON.
      }

      throw new Error(detail);
    }

    if (response.status === 204) {
      return null;
    }

    return response.json();
  }

  async function loadManagedUsers() {
    if (currentUser?.role !== 'admin') {
      return;
    }

    adminUsersLoading = true;
    adminError = '';

    try {
      const data = await adminRequest('/api/admin/users');

      managedUsers = Array.isArray(data)
        ? data.filter((item): item is ManagedUser =>
            item &&
            typeof item.id === 'number' &&
            typeof item.username === 'string' &&
            isUserRole(item.role) &&
            typeof item.is_active === 'boolean'
          )
        : [];
    } catch (cause) {
      adminError =
        cause instanceof Error
          ? cause.message
          : 'Unable to load users.';
    } finally {
      adminUsersLoading = false;
    }
  }

  function openAdminPanel() {
    if (currentUser?.role !== 'admin') {
      return;
    }

    workspaceView = 'admin';
    adminNotice = '';
    adminError = '';
    void loadManagedUsers();

    if (sidebarOpen) {
      sidebarOpen = false;
    }
  }

  async function loadAuditLogs() {
    if (currentUser?.role !== 'admin') {
      return;
    }

    auditLoading = true;
    auditError = '';

    try {
      const params = new URLSearchParams();

      if (auditUsernameFilter.trim()) {
        params.set('username', auditUsernameFilter.trim());
      }

      if (auditStatusFilter.trim()) {
        params.set('status', auditStatusFilter.trim());
      }

      if (auditToolFilter.trim()) {
        params.set('tool', auditToolFilter.trim());
      }

      params.set('limit', '100');

      const data = await adminRequest(
        `/api/admin/audit?${params.toString()}`
      );

      auditLogs = Array.isArray(data)
        ? data.filter((item): item is AuditLogItem =>
            item &&
            typeof item.username === 'string' &&
            typeof item.question === 'string' &&
            typeof item.status === 'string' &&
            typeof item.created_at === 'string'
          )
        : [];
    } catch (cause) {
      auditError =
        cause instanceof Error
          ? cause.message
          : 'Unable to load audit activity.';
    } finally {
      auditLoading = false;
    }
  }

  function openAuditPanel() {
    if (currentUser?.role !== 'admin') {
      return;
    }

    workspaceView = 'audit';
    auditError = '';
    void loadAuditLogs();

    if (sidebarOpen) {
      sidebarOpen = false;
    }
  }

  function clearAuditFilters() {
    auditUsernameFilter = '';
    auditStatusFilter = '';
    auditToolFilter = '';
    void loadAuditLogs();
  }

  function formatAuditTime(value: string): string {
    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleString();
  }

  function auditStatusClass(status: string): string {
    if (status === 'success') {
      return 'success';
    }

    if (status === 'validation_error') {
      return 'warning';
    }

    return 'error';
  }

  function openChatWorkspace() {
    workspaceView = 'chat';
    adminError = '';
    adminNotice = '';

    if (sidebarOpen) {
      sidebarOpen = false;
    }
  }

  async function createManagedUser(event?: SubmitEvent) {
    event?.preventDefault();

    const username = newUserUsername.trim();

    if (!username || newUserPassword.length < 10) {
      adminError = 'Enter a username and a password with at least 10 characters.';
      return;
    }

    adminActionLoading = true;
    adminError = '';
    adminNotice = '';

    try {
      const created = await adminRequest('/api/admin/users', {
        method: 'POST',
        body: JSON.stringify({
          username,
          password: newUserPassword,
          role: newUserRole
        })
      });

      if (created) {
        managedUsers = [...managedUsers, created as ManagedUser]
          .sort((a, b) => a.username.localeCompare(b.username));
      }

      newUserUsername = '';
      newUserPassword = '';
      newUserRole = 'analyst';
      adminNotice = 'User created successfully.';
    } catch (cause) {
      adminError =
        cause instanceof Error
          ? cause.message
          : 'Unable to create user.';
    } finally {
      adminActionLoading = false;
    }
  }

  async function changeManagedUserRole(
    user: ManagedUser,
    role: UserRole
  ) {
    if (role === user.role) {
      return;
    }

    adminActionLoading = true;
    adminError = '';
    adminNotice = '';

    try {
      const updated = await adminRequest(
        `/api/admin/users/${user.id}/role`,
        {
          method: 'PATCH',
          body: JSON.stringify({ role })
        }
      );

      managedUsers = managedUsers.map((item) =>
        item.id === user.id
          ? (updated as ManagedUser)
          : item
      );

      adminNotice = `${user.username}'s role was updated.`;
    } catch (cause) {
      adminError =
        cause instanceof Error
          ? cause.message
          : 'Unable to update role.';
    } finally {
      adminActionLoading = false;
    }
  }

  async function toggleManagedUserStatus(user: ManagedUser) {
    adminActionLoading = true;
    adminError = '';
    adminNotice = '';

    try {
      const updated = await adminRequest(
        `/api/admin/users/${user.id}/status`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            is_active: !user.is_active
          })
        }
      );

      managedUsers = managedUsers.map((item) =>
        item.id === user.id
          ? (updated as ManagedUser)
          : item
      );

      adminNotice = `${user.username} is now ${updated.is_active ? 'active' : 'inactive'}.`;
    } catch (cause) {
      adminError =
        cause instanceof Error
          ? cause.message
          : 'Unable to update account status.';
    } finally {
      adminActionLoading = false;
    }
  }

  function startPasswordReset(user: ManagedUser) {
    resetPasswordUserId = user.id;
    resetPasswordValue = '';
    adminError = '';
    adminNotice = '';
  }

  function cancelPasswordReset() {
    resetPasswordUserId = null;
    resetPasswordValue = '';
  }

  async function submitPasswordReset(user: ManagedUser) {
    if (resetPasswordValue.length < 10) {
      adminError = 'The new password must contain at least 10 characters.';
      return;
    }

    adminActionLoading = true;
    adminError = '';
    adminNotice = '';

    try {
      await adminRequest(
        `/api/admin/users/${user.id}/reset-password`,
        {
          method: 'POST',
          body: JSON.stringify({
            new_password: resetPasswordValue
          })
        }
      );

      resetPasswordUserId = null;
      resetPasswordValue = '';
      adminNotice = `${user.username}'s password was reset.`;
    } catch (cause) {
      adminError =
        cause instanceof Error
          ? cause.message
          : 'Unable to reset password.';
    } finally {
      adminActionLoading = false;
    }
  }

  async function copyAnswer(message: Message) {
    try {
      await navigator.clipboard.writeText(message.text);
      copyNotice = message.id;
    } catch {
      copyNotice = null;
      exportNotice = 'Unable to copy: allow clipboard access for localhost.';
    }
  }

  function downloadTranscript() {
    const active = conversations.find((c) => c.id === activeConversationId);
    if (!active || active.messages.length === 0) {
      exportNotice = 'Start a conversation before exporting a transcript.';
      return;
    }
    const text = [
      `Bundle Data Assistant — ${active.title}`,
      '',
      ...active.messages.map((message) =>
        `${message.role === 'user' ? 'You' : 'Bundle Assistant'}:\n${message.text}\n`
      )
    ].join('\n');
    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'bundle-conversation.txt';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    exportNotice = '';
  }

</script>





<svelte:head>

  <title>Bundle Data Assistant</title>



  <meta

    name="description"

    content="AI-powered financial and order data assistant"

  />



  <meta name="theme-color" content="#070d1b" />
  <meta

    name="viewport"

    content="width=device-width, initial-scale=1"

  />

</svelte:head>





{#if !authToken}

  <div class="login-page">
    <div class="noir-atmosphere" aria-hidden="true"><div class="noir-atmosphere-grid"></div><div class="noir-orbit noir-orbit-one"></div><div class="noir-orbit noir-orbit-two"></div><div class="noir-light"></div></div>
    <div class="login-orb orb-one" aria-hidden="true"></div>
    <div class="login-orb orb-two" aria-hidden="true"></div>
    <div class="login-shell">
      <section class="login-showcase" aria-label="Bundle platform introduction">
        <div class="showcase-eyebrow"><span class="pulse-point"></span> BUNDLE / INTELLIGENCE PLATFORM <span class="version-tag">V 2.1 / NOIR</span></div>
        <!-- Pure CSS decorative instrument: no external assets or fake data. -->
        <div class="noir-instrument" aria-hidden="true">
          <div class="instrument-arc instrument-arc-outer"></div>
          <div class="instrument-arc instrument-arc-middle"></div>
          <div class="instrument-arc instrument-arc-inner"></div>
          <div class="instrument-crosshair"></div>
          <div class="instrument-core"><span class="instrument-glyph">B</span><span class="instrument-core-caption">DATA / INTELLIGENCE</span></div>
          <div class="instrument-coordinate instrument-coordinate-top">N / 01 — SIGNAL</div>
          <div class="instrument-coordinate instrument-coordinate-bottom">SECURE · INTELLIGENT · CONNECTED</div>
        </div>
        <div class="showcase-hero">
          <div class="showcase-micro">A CLEARER VIEW OF YOUR BUSINESS</div>
          <h2>Your data.<br /><em>Your next insight.</em></h2>
          <p>Ask questions, uncover insights, and make smarter decisions with AI — powered by your company data.</p>
        </div>
        <div class="showcase-product" aria-label="Platform capabilities">
          <div class="product-heading"><span class="product-indicator"></span> ONE CONNECTED WORKSPACE <span class="product-version">BUNDLE / 02</span></div>
          <div class="product-main">
            <div class="product-label">WHAT YOU CAN DO</div>
            <strong>Find clarity in complex data.</strong>
            <p>Query your datasets, explore trends and work with decisions grounded in actual records.</p>
          </div>
          <div class="product-rows">
            <div><span class="product-num">01</span><span>Ask questions in natural language</span><span class="product-arrow">↗</span></div>
            <div><span class="product-num">02</span><span>Explore reporting and trends</span><span class="product-arrow">↗</span></div>
            <div><span class="product-num">03</span><span>Work with connected data</span><span class="product-arrow">↗</span></div>
          </div>
        </div>
        <div class="showcase-foot">
          <div><span class="foot-symbol">✧</span> Ask in natural language</div>
          <div><span class="foot-symbol">◎</span> Charts and real insights</div>
          <div><span class="foot-symbol">◇</span> Secure workspace</div>
        </div>
      </section>
      <section class="login-panel" aria-label="Sign in">
        <div class="login-card">

      <div class="login-brand">
        <div class="login-logo">
          <svg class="bundle-mark-svg" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
            <path d="M18 10h17c11 0 17 6 17 15 0 6-3 10-8 13 6 2 10 6 10 13 0 10-8 17-20 17H18V10Zm9 9v14h8c5 0 8-3 8-7s-3-7-8-7h-8Zm0 22v17h9c6 0 9-3 9-8s-3-9-9-9h-9Z" transform="translate(0 -6) scale(1 .98)" fill="currentColor"/>
            <path d="M11 14v36" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" opacity=".44"/>
          </svg>
</div>

        <div>
          <h1>Bundle</h1>
          <p>Data Assistant</p>
        </div>
      </div>

      <div class="login-heading">
        <div class="section-kicker">YOUR WORKSPACE / BUNDLE</div>
        <h2>Welcome <span>back.</span></h2>
        <p>Sign in to your Bundle workspace to explore connected business intelligence.</p>
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
            placeholder="Enter your username"
            disabled={loggingIn}
            required
          />
        </label>

        <label class="password-field">
          Password
          <span class="password-input-wrap">
            <input
              type={revealPassword ? 'text' : 'password'}
              bind:value={loginPassword}
              autocomplete="current-password"
              placeholder="Enter your password"
              disabled={loggingIn}
              required
            />
            <button type="button" class="password-toggle" onclick={() => revealPassword = !revealPassword} aria-label={revealPassword ? 'Hide password' : 'Show password'} aria-pressed={revealPassword}>
              {revealPassword ? 'HIDE' : 'SHOW'}
            </button>
          </span>
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
          <span>{loggingIn ? 'Authenticating...' : 'Sign in to workspace'}</span><span aria-hidden="true">↗</span>
        </button>

      </form>
      <div class="login-security"><span class="security-lock" aria-hidden="true">✦</span> WORKSPACE ACCESS · AUTHENTICATED SIGN IN <span> / BUNDLE</span></div>
    </div>
    </section>
    </div>
  </div>

{:else}

<div class="app">
  <div class="noir-atmosphere workspace-atmosphere" aria-hidden="true"><div class="noir-atmosphere-grid"></div><div class="noir-orbit noir-orbit-one"></div><div class="noir-orbit noir-orbit-two"></div><div class="noir-light"></div><div class="workspace-aura"><span></span><span></span><span></span></div></div>



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
          <svg class="bundle-mark-svg" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
            <path d="M18 10h17c11 0 17 6 17 15 0 6-3 10-8 13 6 2 10 6 10 13 0 10-8 17-20 17H18V10Zm9 9v14h8c5 0 8-3 8-7s-3-7-8-7h-8Zm0 22v17h9c6 0 9-3 9-8s-3-9-9-9h-9Z" transform="translate(0 -6) scale(1 .98)" fill="currentColor"/>
            <path d="M11 14v36" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" opacity=".44"/>
          </svg>
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



      <p class="history-label">WORKSPACE / CONVERSATIONS</p>

      <div class="workspace-switcher">
        <button
          type="button"
          class:active={workspaceView === 'chat'}
          onclick={openChatWorkspace}
        >
          <span>◇</span>
          AI Workspace
        </button>

        {#if currentUser?.role === 'admin'}
          <button
            type="button"
            class:active={workspaceView === 'admin'}
            onclick={openAdminPanel}
          >
            <span>⌘</span>
            User Management
          </button>

          <button
            type="button"
            class:active={workspaceView === 'audit'}
            onclick={openAuditPanel}
          >
            <span>≡</span>
            Audit Logs
          </button>
        {/if}
      </div>

      {#if workspaceView === 'chat'}
      <label class="history-search-label">
        <span class="sr-only">Search conversations</span>
        <span aria-hidden="true">⌕</span>
        <input type="search" bind:value={historyQuery} placeholder="Search chats..." autocomplete="off" />
      </label>



      {#each conversations.filter((conversation) => conversation.title.toLowerCase().includes(historyQuery.trim().toLowerCase())) as conversation (conversation.id)}



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
      {/if}



    </div>





    <div class="sidebar-footer">

  <div class="account-summary">
    <div class="account-avatar">{userInitial()}</div>
    <div class="account-details">
      <strong>{currentUser?.username ?? 'Verifying account'}</strong>
      <span>{roleLabel()} ACCESS</span>
    </div>
    <span class:viewer-role={currentUser?.role === 'viewer'} class="role-chip">
      {roleLabel()}
    </span>
  </div>

  <div class="sidebar-status">
    <div class="status-dot"></div>
    <span>{currentUser?.role === 'viewer' ? 'READ-ONLY WORKSPACE' : 'INTELLIGENCE WORKSPACE'}</span>
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
          <span class="topbar-path">
            WORKSPACE <span>/</span>
            {workspaceView === 'admin'
              ? 'ADMINISTRATION'
              : workspaceView === 'audit'
                ? 'AUDIT'
                : 'AI ASSISTANT'}
          </span>
          <strong>
            {workspaceView === 'admin'
              ? 'User Management'
              : workspaceView === 'audit'
                ? 'Audit Logs'
                : 'AI Assistant'}
          </strong>
          <small>
            {workspaceView === 'admin'
              ? 'Accounts · Roles · Access'
              : workspaceView === 'audit'
                ? 'Activity · Tools · Outcomes'
                : 'Ask · Analyze · Explore · Decide'}
          </small>
        </div>



      </div>



      <div class="topbar-tools">{#if workspaceView === 'chat'}<button type="button" class="transcript-action" onclick={downloadTranscript} title="Download this conversation as a text file" disabled={getMessages().length === 0}>↓ Export chat</button>{/if}<span class="topbar-version">BUNDLE / ENTERPRISE</span><div class:viewer-badge={currentUser?.role === 'viewer'} class="topbar-badge"><span class="badge-led"></span> {currentUser?.role === 'viewer' ? 'READ ONLY' : roleLabel()}</div><div class="topbar-initial" title={currentUser ? `${currentUser.username} · ${roleLabel()}` : 'Signed in'}>{userInitial()}</div></div>



    </header>





    <!-- CHAT AREA -->

    {#if workspaceView === 'chat'}

    <div

      class="chat-area"

      bind:this={chatContainer}

    >



      {#if getMessages().length === 0}



        <!-- WELCOME SCREEN -->



        <div class="welcome">



          <div class="welcome-logo">
          <svg class="bundle-mark-svg" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
            <path d="M18 10h17c11 0 17 6 17 15 0 6-3 10-8 13 6 2 10 6 10 13 0 10-8 17-20 17H18V10Zm9 9v14h8c5 0 8-3 8-7s-3-7-8-7h-8Zm0 22v17h9c6 0 9-3 9-8s-3-9-9-9h-9Z" transform="translate(0 -6) scale(1 .98)" fill="currentColor"/>
            <path d="M11 14v36" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" opacity=".44"/>
          </svg>
</div>



          <div class="welcome-eyebrow"><span class="pulse-point"></span> BUNDLE INTELLIGENCE ENGINE <span class="welcome-version">LIVE WORKSPACE</span></div>
          <h1>Turn questions into<br /><em>intelligence.</em></h1>



          <p>

            Ask a question, explore a pattern, or uncover an insight.<br />
            Your enterprise data, translated into clear, actionable answers.

          </p>






          <section class="dataset-intelligence" aria-label="Active dataset intelligence">
            <div class="dataset-intelligence-head">
              <div>
                <span class="dataset-kicker">ACTIVE DATASET</span>
                <h2>
                  {businessProfile?.dataset_name?.replaceAll('_', ' ') ?? 'Company intelligence'}
                </h2>
              </div>

              <button
                type="button"
                class="dataset-refresh"
                onclick={() => void loadBusinessProfile()}
                disabled={businessProfileLoading}
              >
                {businessProfileLoading ? 'Refreshing…' : '↻ Refresh'}
              </button>
            </div>

            {#if businessProfileLoading && !businessProfile}
              <div class="dataset-profile-state">
                Loading the latest business profile…
              </div>
            {:else if businessProfileError}
              <div class="dataset-profile-state dataset-profile-error" role="alert">
                <strong>Dataset profile unavailable</strong>
                <span>{businessProfileError}</span>
              </div>
            {:else if businessProfile}
              <div class="dataset-profile-meta">
                <span>
                  <strong>{businessProfile.total_rows.toLocaleString()}</strong>
                  rows
                </span>
                <span>
                  <strong>{businessProfile.primary_measure?.replaceAll('_', ' ') ?? '—'}</strong>
                  primary measure
                </span>
                <span>
                  <strong>{profileDateRange()}</strong>
                  coverage
                </span>
              </div>

              <div class="dataset-quick-summary">
                <span>QUICK EXECUTIVE VIEW</span>
                <p>{businessProfile.quick_summary}</p>
              </div>

              <div class="dataset-profile-actions">
                <button
                  type="button"
                  class="dataset-explain"
                  onclick={() => {
                    businessProfileExpanded = !businessProfileExpanded;
                  }}
                >
                  {businessProfileExpanded ? 'Hide detail' : 'Explain more'}
                  <span>{businessProfileExpanded ? '↑' : '↓'}</span>
                </button>

                <small>
                  Database-grounded profile · no AI inference
                </small>
              </div>

              {#if businessProfileExpanded}
                <div class="dataset-deep-analysis">
                  <section>
                    <span class="dataset-detail-title">MEASURES</span>

                    <div class="dataset-measure-grid">
                      {#each businessProfile.measures.slice(0, 6) as measure}
                        <article>
                          <span>{measure.column_name.replaceAll('_', ' ')}</span>
                          <strong>{formatProfileNumber(measure.total)}</strong>
                          <small>
                            Avg {formatProfileNumber(measure.average)}
                          </small>
                        </article>
                      {/each}
                    </div>
                  </section>

                  {#if businessProfile.category_breakdowns.length > 0}
                    <section>
                      <span class="dataset-detail-title">TOP BREAKDOWNS</span>

                      <div class="dataset-breakdown-grid">
                        {#each businessProfile.category_breakdowns.slice(0, 4) as breakdown}
                          <article class="dataset-breakdown-card">
                            <div>
                              <strong>{breakdown.category_column.replaceAll('_', ' ')}</strong>
                              <span>by {breakdown.measure_column.replaceAll('_', ' ')}</span>
                            </div>

                            <ol>
                              {#each breakdown.values.slice(0, 3) as item}
                                <li>
                                  <span>{item.name}</span>
                                  <strong>{formatProfileNumber(item.total)}</strong>
                                </li>
                              {/each}
                            </ol>
                          </article>
                        {/each}
                      </div>
                    </section>
                  {/if}
                </div>
              {/if}
            {:else}
              <div class="dataset-profile-state">
                No generated business profile is available yet.
              </div>
            {/if}
          </section>

          <div class="welcome-capabilities" aria-label="Supported capabilities"><span><b>✦</b> Natural language</span><span><b>◈</b> Analytics</span><span><b>◎</b> Data visualization</span></div>
          <div class="suggestion-label">EXPLORE YOUR DATA <span>SELECT A PROMPT ↘</span></div>
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



          <div class="conversation-banner"><div><span class="banner-overline">ACTIVE SESSION</span><h2>Intelligence thread</h2><p>Results are generated from your connected data sources.</p></div><div class="banner-glow" aria-hidden="true">✦</div></div>
          {#each getMessages() as message (message.id)}



            <div

              class="message-row"

              class:user-row={message.role === 'user'}

            >



              {#if message.role === 'assistant'}



                <div class="assistant-avatar">
          <svg class="bundle-mark-svg" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
            <path d="M18 10h17c11 0 17 6 17 15 0 6-3 10-8 13 6 2 10 6 10 13 0 10-8 17-20 17H18V10Zm9 9v14h8c5 0 8-3 8-7s-3-7-8-7h-8Zm0 22v17h9c6 0 9-3 9-8s-3-9-9-9h-9Z" transform="translate(0 -6) scale(1 .98)" fill="currentColor"/>
            <path d="M11 14v36" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" opacity=".44"/>
          </svg>
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
                  {@html renderAssistantText(message.text)}
                </div>

                {#if message.role === 'assistant'}
                  <div class="reply-actions">
                    <button type="button" onclick={() => copyAnswer(message)} aria-label="Copy assistant answer">
                      {copyNotice === message.id ? '✓ Copied' : '⧉ Copy answer'}
                    </button>

                    {#if (message.source === 'active_dataset' || message.source === 'rag' || message.source === 'hybrid' || message.source === 'forecast' || message.source === 'scenario') && message.question}
                      <button
                        type="button"
                        class="explain-more-button"
                        onclick={() => void requestDeepAnalysis(message)}
                        disabled={message.deepLoading}
                        aria-label="Explain this answer in more detail"
                      >
                        {message.deepLoading
                          ? 'Analyzing…'
                          : message.deepAnswer
                            ? '↻ Refresh detail'
                            : '✦ Explain more'}
                      </button>
                    {/if}
                  </div>

                  {#if message.deepError}
                    <div class="deep-analysis-error" role="alert">
                      {message.deepError}
                    </div>
                  {/if}

                  {#if message.deepAnswer}
                    <section class="deep-analysis-panel">
                      <div class="deep-analysis-label">
                        DEEP ANALYSIS
                      </div>

                      <p class="deep-analysis-text">
                        {@html renderAssistantText(message.deepAnswer)}
                      </p>

                      <div class="deep-analysis-footnote">
                        {message.source === 'rag'
                          ? 'Based only on authorized retrieved document evidence.'
                          : message.source === 'hybrid'
                            ? 'Based on permitted structured metrics plus authorized document evidence.'
                            : message.source === 'forecast'
                              ? 'Based on the deterministic forecast engine, historical data, uncertainty range, and back-test diagnostics.'
                              : message.source === 'scenario'
                                ? 'Hypothetical what-if analysis based on the current database baseline and explicit assumptions; this is not a forecast.'
                                : 'Based only on structured evidence returned by the active dataset.'}
                      </div>
                    </section>
                  {/if}

                  {#if message.citations && message.citations.length > 0}
                    <section class="rag-citations" aria-label="Document evidence">
                      <div class="rag-citations-title">
                        DOCUMENT EVIDENCE
                      </div>

                      {#each message.citations as citation}
                        <div class="rag-citation-row">
                          <span class="rag-citation-index">
                            [{citation.index}]
                          </span>

                          <div class="rag-citation-copy">
                            <strong>
                              {citation.title || citation.document_id}
                            </strong>

                            <small>
                              {citation.document_id}
                              {citation.document_type
                                ? ` · ${citation.document_type}`
                                : ''}
                              {typeof citation.similarity === 'number'
                                ? ` · similarity ${citation.similarity.toFixed(3)}`
                                : ''}
                            </small>
                          </div>
                        </div>
                      {/each}
                    </section>
                  {/if}
                {/if}





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
    ><div class="result-card-header"><span class="result-eyebrow"><span class="mini-diamond">◆</span> ANALYTICS / LIVE INSIGHTS</span><span class="result-records">{message.rows.length} data {message.rows.length === 1 ? 'point' : 'points'}</span></div><div class="chart-canvas">
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
          <svg class="bundle-mark-svg" viewBox="0 0 64 64" aria-hidden="true" focusable="false">
            <path d="M18 10h17c11 0 17 6 17 15 0 6-3 10-8 13 6 2 10 6 10 13 0 10-8 17-20 17H18V10Zm9 9v14h8c5 0 8-3 8-7s-3-7-8-7h-8Zm0 22v17h9c6 0 9-3 9-8s-3-9-9-9h-9Z" transform="translate(0 -6) scale(1 .98)" fill="currentColor"/>
            <path d="M11 14v36" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" opacity=".44"/>
          </svg>
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

      {#if currentUser?.role === 'viewer'}
        <div class="viewer-notice" role="status">
          <span class="viewer-notice-icon">◇</span>
          <div>
            <strong>Read-only access</strong>
            <span>You can review existing conversations and exported results. AI questions require Analyst or Admin access.</span>
          </div>
        </div>
      {/if}

      <form

        class="input-box"

        onsubmit={sendMessage}

      >



        <textarea

          bind:value={input}

          onkeydown={handleKeydown}

          placeholder={currentUser?.role === 'viewer'
            ? 'Viewer access is read-only'
            : authProfileLoading
              ? 'Verifying workspace permissions...'
              : 'Ask Bundle anything about your company data...'}

          aria-label="Your message"

          rows="1"

          disabled={sending || !canUseChat()}

        ></textarea>





        <button

          class="send-button"

          type="submit"

          disabled={sending || !input.trim() || !canUseChat()}

          aria-label="Send message"

        >



          {sending ? '…' : '↑'}



        </button>



      </form>





      {#if exportNotice}
        <p class="export-notice" role="status">{exportNotice}</p>
      {/if}
      <p class="input-hint">



        {currentUser?.role === 'viewer'
          ? 'BUNDLE VIEWER · Read-only workspace access.'
          : 'BUNDLE INTELLIGENCE · Answers are generated from the connected data. Verify consequential decisions against source records.'}



      </p>



    </div>

    {:else if workspaceView === 'admin' && currentUser?.role === 'admin'}

      <section class="admin-workspace">
        <div class="admin-hero">
          <div>
            <span class="admin-overline">BUNDLE ACCESS CONTROL</span>
            <h1>User management</h1>
            <p>Manage workspace accounts, roles, account status, and password resets.</p>
          </div>
          <button
            type="button"
            class="admin-refresh"
            onclick={() => void loadManagedUsers()}
            disabled={adminUsersLoading || adminActionLoading}
          >
            {adminUsersLoading ? 'Refreshing…' : '↻ Refresh users'}
          </button>
        </div>

        {#if adminError}
          <div class="admin-alert admin-alert-error" role="alert">{adminError}</div>
        {/if}

        {#if adminNotice}
          <div class="admin-alert admin-alert-success" role="status">{adminNotice}</div>
        {/if}

        <div class="admin-grid">
          <section class="admin-card admin-create-card">
            <div class="admin-card-heading">
              <div>
                <span>NEW ACCOUNT</span>
                <h2>Create user</h2>
              </div>
              <div class="admin-card-icon">＋</div>
            </div>

            <form class="admin-create-form" onsubmit={createManagedUser}>
              <label>
                <span>Username</span>
                <input
                  type="text"
                  bind:value={newUserUsername}
                  autocomplete="off"
                  placeholder="e.g. analyst3"
                  maxlength="100"
                  disabled={adminActionLoading}
                  required
                />
              </label>

              <label>
                <span>Temporary password</span>
                <input
                  type="password"
                  bind:value={newUserPassword}
                  autocomplete="new-password"
                  placeholder="Minimum 10 characters"
                  minlength="10"
                  maxlength="200"
                  disabled={adminActionLoading}
                  required
                />
              </label>

              <label>
                <span>Role</span>
                <select bind:value={newUserRole} disabled={adminActionLoading}>
                  <option value="analyst">Analyst</option>
                  <option value="viewer">Viewer</option>
                  <option value="admin">Admin</option>
                </select>
              </label>

              <button
                type="submit"
                class="admin-primary-action"
                disabled={adminActionLoading}
              >
                {adminActionLoading ? 'Working…' : 'Create account'}
              </button>
            </form>
          </section>

          <section class="admin-card admin-summary-card">
            <div class="admin-card-heading">
              <div>
                <span>ACCESS OVERVIEW</span>
                <h2>Workspace users</h2>
              </div>
              <div class="admin-card-icon">◎</div>
            </div>

            <div class="admin-metrics">
              <div>
                <strong>{managedUsers.length}</strong>
                <span>Total users</span>
              </div>
              <div>
                <strong>{managedUsers.filter((user) => user.is_active).length}</strong>
                <span>Active</span>
              </div>
              <div>
                <strong>{managedUsers.filter((user) => user.role === 'admin').length}</strong>
                <span>Admins</span>
              </div>
            </div>

            <p class="admin-security-note">
              Role changes and account status are enforced by the FastAPI backend. Hiding controls here is not the security boundary.
            </p>
          </section>
        </div>

        <section class="admin-card admin-users-card">
          <div class="admin-card-heading admin-users-heading">
            <div>
              <span>DIRECTORY</span>
              <h2>Accounts</h2>
            </div>
            <span class="admin-user-count">{managedUsers.length} USERS</span>
          </div>

          {#if adminUsersLoading}
            <div class="admin-empty-state">Loading workspace users…</div>
          {:else if managedUsers.length === 0}
            <div class="admin-empty-state">No user accounts were returned.</div>
          {:else}
            <div class="admin-user-list">
              {#each managedUsers as user (user.id)}
                <article class="admin-user-row">
                  <div class="admin-user-identity">
                    <div class="admin-user-avatar">{user.username.charAt(0).toUpperCase()}</div>
                    <div>
                      <strong>{user.username}</strong>
                      <span>ID #{user.id} · {user.is_active ? 'Active' : 'Inactive'}</span>
                    </div>
                  </div>

                  <label class="admin-inline-field">
                    <span>Role</span>
                    <select
                      value={user.role}
                      onchange={(event) =>
                        void changeManagedUserRole(
                          user,
                          (event.currentTarget as HTMLSelectElement).value as UserRole
                        )
                      }
                      disabled={adminActionLoading || user.id === currentUser?.id}
                    >
                      <option value="admin">Admin</option>
                      <option value="analyst">Analyst</option>
                      <option value="viewer">Viewer</option>
                    </select>
                  </label>

                  <div class="admin-status-cell">
                    <span class:inactive={!user.is_active} class="admin-status-pill">
                      <i></i>
                      {user.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </div>

                  <div class="admin-row-actions">
                    <button
                      type="button"
                      onclick={() => void toggleManagedUserStatus(user)}
                      disabled={adminActionLoading || user.id === currentUser?.id}
                    >
                      {user.is_active ? 'Deactivate' : 'Activate'}
                    </button>
                    <button
                      type="button"
                      onclick={() => startPasswordReset(user)}
                      disabled={adminActionLoading}
                    >
                      Reset password
                    </button>
                  </div>

                  {#if resetPasswordUserId === user.id}
                    <div class="admin-reset-panel">
                      <label>
                        <span>New password for {user.username}</span>
                        <input
                          type="password"
                          bind:value={resetPasswordValue}
                          minlength="10"
                          maxlength="200"
                          autocomplete="new-password"
                          placeholder="Minimum 10 characters"
                        />
                      </label>
                      <button
                        type="button"
                        class="admin-primary-action"
                        onclick={() => void submitPasswordReset(user)}
                        disabled={adminActionLoading}
                      >
                        Save password
                      </button>
                      <button
                        type="button"
                        onclick={cancelPasswordReset}
                        disabled={adminActionLoading}
                      >
                        Cancel
                      </button>
                    </div>
                  {/if}
                </article>
              {/each}
            </div>
          {/if}
        </section>
      </section>

    {:else if workspaceView === 'audit' && currentUser?.role === 'admin'}

      <section class="audit-workspace">
        <div class="admin-hero audit-hero">
          <div>
            <span class="admin-overline">BUNDLE SECURITY ACTIVITY</span>
            <h1>Audit logs</h1>
            <p>Review recent AI requests, tools used, execution outcomes, and response timing.</p>
          </div>

          <button
            type="button"
            class="admin-refresh"
            onclick={() => void loadAuditLogs()}
            disabled={auditLoading}
          >
            {auditLoading ? 'Refreshing…' : '↻ Refresh logs'}
          </button>
        </div>

        <section class="admin-card audit-filter-card">
          <form
            class="audit-filter-grid"
            onsubmit={(event) => {
              event.preventDefault();
              void loadAuditLogs();
            }}
          >
            <label>
              <span>Username</span>
              <input
                type="search"
                bind:value={auditUsernameFilter}
                placeholder="All users"
              />
            </label>

            <label>
              <span>Status</span>
              <select bind:value={auditStatusFilter}>
                <option value="">All statuses</option>
                <option value="success">Success</option>
                <option value="validation_error">Validation error</option>
                <option value="error">Error</option>
              </select>
            </label>

            <label>
              <span>Tool</span>
              <input
                type="search"
                bind:value={auditToolFilter}
                placeholder="e.g. get_monthly_trend"
              />
            </label>

            <button
              type="submit"
              class="admin-primary-action"
              disabled={auditLoading}
            >
              Apply filters
            </button>

            <button
              type="button"
              class="admin-refresh"
              onclick={clearAuditFilters}
              disabled={auditLoading}
            >
              Clear
            </button>
          </form>
        </section>

        {#if auditError}
          <div class="admin-alert admin-alert-error" role="alert">{auditError}</div>
        {/if}

        <section class="admin-card audit-table-card">
          <div class="admin-card-heading audit-table-heading">
            <div>
              <span>RECENT ACTIVITY</span>
              <h2>Request history</h2>
            </div>
            <span class="admin-user-count">{auditLogs.length} RECORDS</span>
          </div>

          {#if auditLoading}
            <div class="admin-empty-state">Loading audit activity…</div>
          {:else if auditLogs.length === 0}
            <div class="admin-empty-state">No audit records match the current filters.</div>
          {:else}
            <div class="audit-table-scroll">
              <table class="audit-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>User</th>
                    <th>Question</th>
                    <th>Tool</th>
                    <th>Status</th>
                    <th>Time ms</th>
                  </tr>
                </thead>
                <tbody>
                  {#each auditLogs as log}
                    <tr>
                      <td class="audit-time">{formatAuditTime(log.created_at)}</td>
                      <td><strong>{log.username}</strong></td>
                      <td>
                        <div class="audit-question" title={log.question}>
                          {log.question}
                        </div>
                        {#if log.error_message}
                          <div class="audit-error-detail">{log.error_message}</div>
                        {/if}
                      </td>
                      <td><code>{log.tool_name ?? 'no_tool'}</code></td>
                      <td>
                        <span class={`audit-status ${auditStatusClass(log.status)}`}>
                          {log.status.replaceAll('_', ' ')}
                        </span>
                      </td>
                      <td>{log.execution_time_ms ?? '—'}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </section>
      </section>

    {/if}



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





/* =======================================================
   BUNDLE / FUTURE INTERFACE - DESIGN SYSTEM 2026
   UI-only changes: existing API + data logic preserved.
   ======================================================= */
:global(html),:global(body){background:#070d1b;color:#eef4ff}
:global(body){font-family:Inter,'Segoe UI',Arial,sans-serif;letter-spacing:-.012em}
:global(button),:global(input),:global(textarea){font-family:inherit}
:global(button:focus-visible),:global(input:focus-visible),:global(textarea:focus-visible){outline:2px solid #65e9ea;outline-offset:3px}
.login-page{min-height:100dvh;position:relative;overflow:hidden;display:flex;align-items:center;justify-content:center;padding:30px;background:radial-gradient(ellipse at 3% 0%,#173156 0%,transparent 45%),radial-gradient(ellipse at 99% 99%,#261f4e 0%,transparent 40%),#060b18;color:#e9f3ff}
.login-page:before,.app:before{content:'';position:absolute;inset:0;pointer-events:none;background-image:linear-gradient(rgba(136,193,245,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(136,193,245,.035) 1px,transparent 1px);background-size:50px 50px;mask-image:linear-gradient(to bottom,#000,transparent 88%)}
.login-orb{position:absolute;border-radius:50%;filter:blur(80px);pointer-events:none;opacity:.3}.orb-one{width:340px;height:340px;left:-115px;top:-150px;background:#268dff}.orb-two{width:290px;height:290px;right:-100px;bottom:-70px;background:#7842ff}
.login-shell{display:grid;grid-template-columns:1.07fr 0.93fr;width:min(1080px,100%);min-height:670px;position:relative;isolation:isolate;border:1px solid rgba(164,197,250,.16);border-radius:24px;overflow:hidden;background:rgba(12,20,39,.91);box-shadow:0 45px 120px #0008,0 0 0 1px #ffffff05;backdrop-filter:blur(24px)}
.login-showcase{position:relative;min-height:640px;display:flex;flex-direction:column;padding:40px 42px;background:radial-gradient(ellipse at 50% 60%,rgba(41,87,166,.2),transparent 58%),linear-gradient(155deg,#111f3a 0%,#10182e 65%,#11132a 100%);border-right:1px solid #d6e8ff16;overflow:hidden}
.login-showcase:after{content:'';position:absolute;inset:0;background:linear-gradient(120deg,transparent 35%,rgba(107,235,255,.045) 50%,transparent 65%);pointer-events:none}
.showcase-eyebrow,.section-kicker,.showcase-micro,.welcome-eyebrow,.suggestion-label{font-size:10px;letter-spacing:.19em;font-weight:800;color:#63dbef;display:flex;align-items:center;gap:11px}
.version-tag{color:#a3b8d6;border:1px solid #c7e5ff28;border-radius:40px;padding:4px 8px;letter-spacing:.08em;margin-left:auto}.pulse-point,.badge-led{display:inline-block;width:7px;height:7px;min-width:7px;background:#57e5d5;border-radius:50%;box-shadow:0 0 11px #57e5d5,0 0 20px #57e5d555}
.showcase-hero{margin-top:74px;position:relative;z-index:2}.showcase-micro{color:#9aaccc}.showcase-hero h2{font-size:clamp(44px,4.8vw,70px);line-height:1.03;margin:18px 0 20px;font-weight:750;letter-spacing:-.068em;color:#f3f8ff}.showcase-hero h2 em,.welcome h1 em{font-style:normal;background:linear-gradient(100deg,#86ffff,#6fa4fa 60%,#b4a3ff);background-clip:text;color:transparent}.showcase-hero p{font-size:14px;max-width:355px;line-height:1.8;color:#9aaccb}
.showcase-foot{display:flex;gap:16px;justify-content:space-between;border-top:1px solid #bdd8fc24;padding-top:23px;color:#93a7c4;font-size:10px;position:relative;z-index:2}.foot-symbol{color:#56e3f1;margin-right:5px;font-size:15px}
.login-panel{display:flex;justify-content:center;align-items:center;padding:38px 52px;position:relative}.login-card{max-width:380px;width:100%;background:none;border:none;box-shadow:none;padding:0;color:#ecf5ff}.login-brand{gap:12px;margin-bottom:78px}.login-logo,.brand-icon,.welcome-logo{background:linear-gradient(145deg,#76eaff,#5374ed) !important;color:#051029 !important;box-shadow:0 10px 35px #218cfb3b;font-weight:900;border:1px solid #abfaff80}.login-logo{width:45px;height:45px;border-radius:14px;font-size:24px}.login-brand h1{color:#fff;margin:0;font-size:22px;font-weight:850;letter-spacing:-.05em}.login-brand p{color:#97aaca;margin:1px 0;font-size:11px;letter-spacing:.09em;text-transform:uppercase}.login-heading{margin-bottom:32px}.login-heading h2{font-weight:750;font-size:clamp(30px,3vw,40px);letter-spacing:-.06em;margin:15px 0 10px;color:#f4f9ff}.login-heading h2 span{color:#7ae5f2}.login-heading p{color:#93a8c8;font-size:13px;line-height:1.8;max-width:300px}.login-form{gap:22px}.login-form label{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#acc4e6;font-weight:700;gap:10px}.login-form input{width:100%;height:51px;box-sizing:border-box;background:#0b152a;border:1px solid #253756;border-radius:11px;padding:0 16px;color:#eef7ff;font-size:14px;letter-spacing:normal}.login-form input::placeholder{color:#637998}.login-form input:focus{border-color:#60c7f2;box-shadow:0 0 0 4px #49cbff16;outline:none}.password-input-wrap{position:relative;display:block}.password-input-wrap input{padding-right:65px}.password-toggle{position:absolute;right:12px;top:50%;transform:translateY(-50%);background:transparent;border:0;color:#73d7ec;font-weight:800;cursor:pointer;font-size:10px;letter-spacing:.1em}.login-button{height:53px;border:1px solid #9cf9ff5c;border-radius:11px;display:flex;align-items:center;justify-content:space-between;padding:0 20px;background:linear-gradient(110deg,#6bd8ee,#6e8eff);color:#06152b;font-size:13px;font-weight:850;box-shadow:0 12px 42px #4d96ff45;transition:transform .2s,box-shadow .2s}.login-button:hover:not(:disabled){transform:translateY(-2px);box-shadow:0 16px 50px #4d96ff6a}.login-button span:last-child{font-size:19px}.login-button:disabled{opacity:.55;cursor:not-allowed}.login-error{background:#842e3b33;color:#ffb0b8;border:1px solid #ff8e9a3d;padding:12px;border-radius:10px}.login-security{border-top:1px solid #c2dcfa19;margin-top:44px;padding-top:22px;font-size:9px;letter-spacing:.1em;color:#7e96b5;white-space:normal}.login-security span:last-child{color:#67d7ec}.security-lock{color:#5de1d9;margin-right:6px}
.app{position:relative;background:#080e1b;color:#e3eefc}.sidebar{width:277px;background:#0a1425;border-right:1px solid #263653;box-shadow:8px 0 55px #0002}.sidebar-header{padding:29px 19px 15px}.brand{padding:0 5px 27px;gap:13px}.brand-icon{width:42px;height:42px;border-radius:13px;font-size:23px}.brand strong{font-size:21px;color:#fff;letter-spacing:-.05em;font-weight:800}.brand span{color:#7895ba;font-size:10px;letter-spacing:.15em;text-transform:uppercase}.new-chat{background:linear-gradient(115deg,#60d2ed,#7688ff);color:#071525;border:1px solid #87ebf5aa;border-radius:11px;font-weight:800;min-height:46px;box-shadow:0 8px 25px #367dec25}.new-chat:hover{background:linear-gradient(115deg,#83e6f4,#9aa6ff)}.history{padding:12px 12px 18px}.history-label{font-size:9px;color:#657f9e;letter-spacing:.18em;padding:0 12px;margin:20px 0 14px}.history-item{color:#9fb5d1;padding:13px;border:1px solid transparent;border-radius:10px}.history-icon{color:#64dced}.history-item:hover{background:#14253b;color:#e9f6ff}.history-item.active{color:#fff;background:#152940;border-color:#4acafc3a;font-weight:600}.sidebar-footer{padding:20px;border-top:1px solid #27344e;display:flex;flex-direction:column;align-items:stretch;gap:14px}.sidebar-status{color:#93b5d0;font-size:10px;font-weight:700;letter-spacing:.065em}.status-dot{background:#5fe6b7;box-shadow:0 0 12px #5fe6b750}.logout-button{border:1px solid #2a3b58;background:#101c31;color:#afc5df;border-radius:10px;min-height:39px;font-weight:650}.logout-button:hover{background:#1b2941;color:#fff}
.main{position:relative;min-width:0;background:radial-gradient(ellipse at 75% 2%,#182b52 0%,transparent 42%),#091120;color:#e9f2fc}.topbar{height:76px;padding:0 34px;border-bottom:1px solid #ffffff14;background:#0b1627aa;backdrop-filter:blur(15px)}.topbar-title{font-size:14px;font-weight:720;color:#e9f6ff}.topbar-path{font-size:10px;letter-spacing:.15em;color:#6d849f;margin-right:9px;font-weight:700}.topbar-path span{color:#4fc5e1;margin:0 7px}.topbar-badge{border:1px solid #57f1e044;color:#79e9da;background:#3aeac20d;letter-spacing:.11em;font-size:10px;font-weight:800;border-radius:40px;display:flex;align-items:center;gap:9px;padding:8px 13px}.chat-area{position:relative;padding:30px 36px;scrollbar-color:#294667 transparent}.welcome{max-width:920px;margin:auto;padding:clamp(12px,5vh,50px) 10px;text-align:center}.welcome-logo{width:80px;height:80px;margin:0 auto 24px;border-radius:25px;font-size:40px;transform:rotate(-7deg);box-shadow:0 0 80px #5aa9ff2f}.welcome-eyebrow{justify-content:center;margin-bottom:17px}.welcome h1{font-size:clamp(35px,5vw,65px);letter-spacing:-.065em;font-weight:760;line-height:1.12;margin:5px auto 19px;color:#edf7ff}.welcome p{color:#9aafc8;line-height:1.8;font-size:15px;max-width:560px;margin:0 auto 40px}.suggestion-label{color:#8da7c3;margin:0 0 13px;justify-content:space-between;font-size:10px}.suggestion-label span{color:#6bdff3}.suggestions{max-width:770px;margin:auto;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:13px;text-align:left}.suggestion{min-height:86px;background:linear-gradient(140deg,#14233a,#111c31);border:1px solid #2e4664;color:#bcd1e9;border-radius:13px;padding:18px;display:flex;align-items:center;gap:15px;font-weight:580;line-height:1.5;transition:transform .2s,background .2s,border-color .2s;box-shadow:0 10px 30px #00000012}.suggestion:hover{transform:translateY(-3px);border-color:#6de1f088;background:linear-gradient(140deg,#18314a,#172444);color:#f4faff}.suggestion-icon{display:grid;place-items:center;min-width:32px;height:32px;border-radius:9px;color:#70dbe9;background:#50d7f016;font-size:19px}
.conversation{max-width:900px;margin:0 auto}.message-row{margin-bottom:24px}.assistant-avatar{background:linear-gradient(145deg,#48cddd,#727af4);color:#061827;border-radius:12px}.message-content{color:#d4e6f9}.message-name{color:#80ddf0;font-size:12px;letter-spacing:.03em}.message-text{color:#e0edfb;line-height:1.8}.chart-wrapper,.table-wrapper,.contribution-panel{background:#111f34;border:1px solid #2f4666;border-radius:15px;color:#dceaff;box-shadow:0 20px 45px #0002}.contribution-heading h3,.contribution-details strong{color:#e7f4ff}.contribution-heading span,.contribution-note,.rank-number{color:#91abc8}.contribution-track{background:#263753}.contribution-fill{background:linear-gradient(90deg,#47d9ef,#827bff)}.download-button{color:#bee8f0;background:#142b44;border:1px solid #355e7a;border-radius:9px}.download-button:hover{background:#21405c;border-color:#67d8e4}.input-section{background:#09111ff5;padding:15px 30px 18px;border-top:1px solid #ffffff0c}.input-box{background:#12213a;border:1px solid #35516b;border-radius:15px;box-shadow:0 12px 35px #0003;max-width:900px}.input-box:focus-within{border-color:#56dcea;box-shadow:0 0 0 4px #46bfe715}.input-box textarea{background:transparent;color:#eff8ff}.input-box textarea::placeholder{color:#7895b4}.send-button{background:linear-gradient(145deg,#62d4e4,#7987fa);color:#081329;border-radius:11px}.input-hint{font-size:10px;color:#5f7b9c;letter-spacing:.04em}.error-message{background:#4b2031;color:#ffd2da;border-color:#903d55}.overlay{background:#010714c7}
@media(max-width:960px){.login-shell{grid-template-columns:1fr 1fr}.login-showcase{padding:32px 26px}.login-panel{padding:30px}.showcase-hero{margin-top:50px}.showcase-foot{flex-wrap:wrap}.login-brand{margin-bottom:48px}}
@media(max-width:700px){.login-page{padding:14px;align-items:stretch}.login-shell{grid-template-columns:1fr;min-height:0}.login-showcase{min-height:0;padding:25px 26px 20px;border-right:0;border-bottom:1px solid #d6e8ff16}.showcase-hero{margin-top:25px}.showcase-hero h2{font-size:38px;margin:10px 0}.showcase-hero p{font-size:12px}.showcase-foot,.showcase-micro{display:none}.login-panel{padding:33px 28px 42px}.login-brand{margin-bottom:35px}.login-security{margin-top:34px}.sidebar{width:min(300px,84vw)}.topbar{height:64px;padding:0 15px}.topbar-path{display:none}.topbar-badge{font-size:8px;padding:7px 8px}.chat-area{padding:18px 15px}.welcome{padding:35px 0}.welcome-logo{width:64px;height:64px;font-size:29px;border-radius:20px}.welcome p{font-size:13px;margin-bottom:28px}.suggestions{grid-template-columns:1fr;gap:10px}.suggestion{min-height:63px;padding:13px}.input-section{padding:12px 12px max(12px,env(safe-area-inset-bottom))}.input-hint{letter-spacing:0;font-size:9px}}
@media(prefers-reduced-motion:reduce){.login-button,.suggestion,.contribution-fill{transition:none}}


/* =============================================================
   BUNDLE / AURORA — VISUAL SYSTEM V2
   Overrides the old light-theme rules. Purely visual; APIs untouched.
   ============================================================= */
:global(body){margin:0;background:#050a16;color:#eaf6ff;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
:global(button),:global(input),:global(textarea){font-family:inherit}
:global(button:focus-visible),:global(input:focus-visible),:global(textarea:focus-visible){outline:2px solid #7ce8ff;outline-offset:3px}
.login-page{background:radial-gradient(ellipse at 10% 10%,#122b54 0%,transparent 40%),radial-gradient(ellipse at 100% 100%,#30214f 0%,transparent 44%),#050912}
.login-shell{width:min(1180px,100%);min-height:690px;border-radius:30px;border:1px solid rgba(124,200,255,.21);box-shadow:0 35px 120px #000b,0 0 90px #3a89fb16}
.login-showcase{background:radial-gradient(circle at 45% 70%,#1c426077 0%,transparent 42%),linear-gradient(145deg,#102443,#0b162a 65%,#141c3a);padding:47px}
.login-showcase:before{content:'';position:absolute;inset:0;pointer-events:none;background:linear-gradient(90deg,transparent 49.75%,#6380ad0c 50%,transparent 50.25%),linear-gradient(#83b9fa08 1px,transparent 1px);background-size:54px 54px}
.showcase-hero{margin-top:54px}.showcase-hero h2{font-size:clamp(48px,5vw,80px);line-height:1.035;font-weight:770}
.showcase-hero p{font-size:15px;color:#b1c4df;max-width:410px}
.showcase-foot{position:relative;z-index:3;border-top:1px solid #84c3ef25;padding-top:20px;color:#a7bed7}
.login-panel{background:radial-gradient(ellipse at 90% 0%,#172a4b5e,transparent 55%),#0b1428}
.login-heading h2{font-size:42px}.login-form label{color:#c3d6f2}.login-form input{background:#101f38;border:1px solid #3b567b;height:56px}.login-form input::placeholder{color:#92a9c8}.login-form input:focus{border-color:#64e8f2;box-shadow:0 0 0 4px #58e5eb16}.login-button{height:58px;font-size:14px;letter-spacing:.015em}
.app{background:#070f20}.app:before{z-index:0}.sidebar,.main{z-index:1}
.sidebar{width:284px;max-width:85vw;background:linear-gradient(178deg,#0a1930,#081326 53%,#091529);border-right:1px solid #2c4162}
.sidebar-header{padding:31px 20px 18px}.brand{padding:0 5px 30px}.brand strong{font-size:23px}.brand span{color:#9aafd0}
.new-chat{display:flex;justify-content:center;min-height:50px;gap:12px;box-shadow:0 12px 28px #2389ff28}
.history{scrollbar-width:thin;scrollbar-color:#3c5779 transparent}.history-label{color:#90abc9;letter-spacing:.16em}
.history-item{border-radius:12px;font-size:12px;line-height:1.5;min-height:51px;transition:background .15s,border-color .15s}.history-item.active{background:linear-gradient(90deg,#133c54,#15264a);border-color:#4ec8ea63;box-shadow:inset 3px 0 #61e9ef}
.sidebar-footer{background:#0b1a2f}.sidebar-status{color:#aed0e9}.logout-button{cursor:pointer}
.main{background:radial-gradient(circle at 87% 12%,rgba(66,85,164,.20),transparent 35%),radial-gradient(circle at 3% 96%,rgba(24,142,155,.07),transparent 40%),#080f20}
.topbar{height:90px;padding:0 clamp(18px,3.5vw,60px);background:rgba(8,19,37,.72);border-bottom:1px solid #32476780}
.topbar-title{display:flex;flex-direction:column;gap:4px;align-items:flex-start}.topbar-title strong{font-size:17px;font-weight:760;color:#f1f7ff;line-height:1.2}.topbar-title small{font-size:11px;color:#90a6c3;font-weight:500}.topbar-path{font-size:9px;color:#6dbbd6;letter-spacing:.17em}
.topbar-tools{display:flex;align-items:center;gap:15px}.topbar-version{font-size:9px;color:#7192b6;letter-spacing:.16em;font-weight:750}.topbar-initial{height:36px;width:36px;border-radius:12px;display:grid;place-items:center;color:#defbff;background:linear-gradient(130deg,#204b69,#303f83);border:1px solid #6ac7e566;font-size:14px;font-weight:800}.topbar-badge{white-space:nowrap;background:#153e4940;color:#85ffdc;border-color:#50eac677}.badge-led{box-shadow:0 0 17px #64efc8}
.chat-area{padding:clamp(18px,3.5vw,46px) clamp(18px,5vw,70px);scrollbar-width:thin;scrollbar-color:#355273 transparent}
.welcome{max-width:870px;min-height:100%;display:flex;flex-direction:column;justify-content:center;padding:28px 3px 55px}.welcome-logo{width:84px;height:84px;box-shadow:0 0 0 12px #58cbea0b,0 0 75px #357aff39;transform:none;border-radius:25px}
.welcome-eyebrow{color:#6bdef4;font-size:10px;letter-spacing:.15em}.welcome-version{border:1px solid #63d5f859;color:#aecce2;padding:5px 8px;border-radius:30px;font-size:8px;letter-spacing:.08em}.welcome h1{font-size:clamp(41px,5.1vw,71px);font-weight:790;letter-spacing:-.067em;line-height:1.05;margin-top:20px}.welcome p{font-size:15px;color:#a7c0dc;line-height:1.8;max-width:620px}
.welcome-capabilities{display:flex;flex-wrap:wrap;justify-content:center;gap:11px;margin:-9px auto 39px}.welcome-capabilities span{padding:8px 12px;border:1px solid #375977b8;border-radius:30px;background:#10243b;color:#b7d4e9;font-size:11px}.welcome-capabilities b{color:#56e6ec;margin-right:6px}
.suggestion-label{max-width:790px;width:100%;color:#9fb5d0;font-size:10px}.suggestion-label span{color:#68dff5}.suggestions{max-width:790px;width:100%;gap:14px}.suggestion{background:linear-gradient(135deg,#142a44,#101e36);border-color:#324f71;min-height:102px;border-radius:17px;box-shadow:0 16px 32px #00000023;color:#d1e2f7}.suggestion:hover{border-color:#6deeffaa;background:linear-gradient(145deg,#173a52,#1c2850);box-shadow:0 12px 44px #2059b12e}
.conversation{max-width:1000px}.conversation-banner{position:relative;overflow:hidden;display:flex;align-items:center;justify-content:space-between;background:linear-gradient(112deg,#122b46,#13234b 74%,#1d2a53);border:1px solid #38577d;border-radius:19px;padding:22px 28px;margin-bottom:35px}.conversation-banner:after{content:'';position:absolute;width:210px;height:210px;right:-35px;top:-90px;background:radial-gradient(circle,#27d3e433,transparent 70%);pointer-events:none}.banner-overline{font-size:10px;letter-spacing:.16em;font-weight:800;color:#70e6ed}.conversation-banner h2{margin:7px 0 4px;color:#f1faff;font-size:24px;letter-spacing:-.045em}.conversation-banner p{margin:0;font-size:12px;color:#a9c2dd}.banner-glow{font-size:51px;color:#6deefa;opacity:.74;text-shadow:0 0 29px #70ebff88}
.message-row{margin-bottom:27px;gap:14px}.message-content{min-width:0;color:#e2effe}.message-name{color:#89eafa;margin-bottom:11px;font-size:12px}.message-text{color:#e5f1fe;line-height:1.7;font-size:14px}.assistant-avatar{border:1px solid #8affff65;box-shadow:0 8px 20px #22c0e333}
.user-row .user-message{background:linear-gradient(120deg,#26416c,#343d79) !important;color:#f5fbff !important;border:1px solid #647fc5aa !important;border-radius:18px 18px 5px 18px !important;box-shadow:0 12px 32px #0002 !important;padding:15px 19px !important;max-width:min(80%,640px)}
.user-row .user-message .message-text{color:#f7fbff!important;font-size:14px}.assistant-message{max-width:100%;flex:1}
.chart-wrapper{background:linear-gradient(145deg,#10233c,#101c32)!important;border:1px solid #355476!important;border-radius:19px!important;padding:0!important;min-height:365px;overflow:hidden;box-shadow:0 16px 38px #00000032!important;margin:22px 0 16px}
.result-card-header{display:flex;align-items:center;justify-content:space-between;padding:17px 22px;border-bottom:1px solid #304666bd;gap:10px;flex-wrap:wrap}.result-eyebrow{font-size:10px;font-weight:800;letter-spacing:.14em;color:#a8d6ee;display:inline-flex;gap:9px;align-items:center}.mini-diamond{font-size:13px;color:#64e2ed}.result-records{color:#90a8c5;background:#1d3552;border:1px solid #2e4d70;border-radius:100px;padding:6px 10px;font-size:10px;font-weight:700}.chart-canvas :global(canvas){height:300px;min-height:300px;padding:13px 24px 19px;position:relative}
.table-wrapper{border:1px solid #355476!important;border-radius:17px!important;overflow:auto;background:#102039!important;margin-top:18px;box-shadow:0 12px 30px #0002}.table-wrapper table{width:100%;border-collapse:collapse;background:transparent!important;color:#d5e6fb!important}.table-wrapper th{background:#1b304d!important;color:#a8cbe6!important;font-size:11px!important;text-transform:uppercase;letter-spacing:.06em;border-color:#375171!important;text-align:left}.table-wrapper td{background:transparent!important;color:#e1efff!important;border-color:#284463!important;font-size:13px}.table-wrapper tr:nth-child(even) td{background:#1c32504d!important}.table-wrapper tr:hover td{background:#264a67a8!important}
.contribution-panel{background:#10223a!important;border:1px solid #355476!important;box-shadow:0 16px 38px #0003}.contribution-details strong{color:#e6f5ff}.download-button{background:#102944!important;border:1px solid #397897!important;color:#bdebf7!important}.download-button:hover{background:#214362!important}
.input-section{position:relative;background:linear-gradient(0deg,#071324 65%,#071324ed);border-top:1px solid #294463;padding:16px clamp(16px,5vw,70px) 18px}.input-box{max-width:1000px;background:#142641;border:1px solid #47728e;border-radius:17px;padding:7px 8px 7px 22px;min-height:62px}.input-box textarea{color:#eaf5ff;font-size:14px;line-height:1.5;min-height:38px;padding-top:11px}.input-box textarea::placeholder{color:#9bb3d0}.send-button{background:linear-gradient(135deg,#5ddcea,#8585ff)!important;color:#071426!important;width:43px;height:43px;font-size:23px;font-weight:800;box-shadow:0 6px 22px #4087ff4d}.send-button:disabled{opacity:.5;box-shadow:none}.input-hint{color:#7c9dbc;text-transform:none;letter-spacing:normal;text-align:center;font-size:10px;margin:10px 0 0}
@media(max-width:1000px){.topbar-version{display:none}.sidebar{width:260px}.chat-area{padding:20px 26px}.conversation-banner{padding:19px 22px}}
@media(max-width:700px){.login-shell{min-height:0}.login-showcase{padding:25px}.login-panel{padding:26px}.showcase-hero h2{font-size:42px}.topbar{height:72px;padding:0 17px}.topbar-title small,.topbar-version,.topbar-initial{display:none}.topbar-title strong{font-size:13px}.topbar-path{font-size:8px}.topbar-tools{gap:6px}.chat-area{padding:18px 14px}.welcome{padding:18px 0 37px}.welcome h1{font-size:41px}.welcome-capabilities{margin:0 0 30px;gap:7px}.welcome-capabilities span{font-size:10px;padding:7px 9px}.conversation-banner h2{font-size:19px}.conversation-banner{padding:16px;margin-bottom:24px}.banner-glow{display:none}.chart-canvas{padding:9px;height:270px;min-height:270px}.result-card-header{padding:12px 14px}.input-section{padding:11px 13px 15px}.input-hint{font-size:9px}}
@media(prefers-reduced-motion:reduce){.suggestion,.send-button,.new-chat,.history-item{transition:none!important}}


/* ===========================================================
   AURORA / CELESTIAL FINISH: UI only — no JS/API changes.
   =========================================================== */
:global(html), :global(body) { background:#030918 !important; }
:global(body) { color:#edf7ff; }

/* BUNDLE / NOIR — deliberately restrained black product design */
:global(html),:global(body){background:#080808!important;color:#eeeeee!important;color-scheme:dark}
.login-page,.app{--surface:#101010;--surface-raised:#171717;--stroke:#303030;--text:#f3f3f3;--muted:#989898;--accent:#f4f4f5;font-family:Inter,system-ui,-apple-system,'Segoe UI',sans-serif;color:#efefef;background:#090909!important}
.login-page::before,.login-page::after,.app::before,.app::after,.login-orb,.login-showcase::before,.login-showcase::after,.sidebar::before,.main::before,.main::after{display:none!important;content:none!important;background:none!important}
.login-page{padding:clamp(12px,3vw,46px)!important;overflow-y:auto;align-items:center}
.login-shell{width:min(1220px,100%)!important;min-height:min(760px,calc(100dvh - 70px))!important;background:#111!important;border:1px solid #2b2b2b!important;border-radius:18px!important;box-shadow:0 24px 80px #0009!important;backdrop-filter:none!important;grid-template-columns:minmax(0,1.14fr) minmax(370px,.86fr)!important}
.login-showcase{min-height:610px!important;background:#121212!important;border-right:1px solid #292929!important;padding:clamp(28px,4vw,62px)!important}
.showcase-eyebrow,.showcase-micro,.section-kicker{color:#929292!important;letter-spacing:.11em!important;font-weight:650}
.showcase-eyebrow .pulse-point,.product-indicator{background:#e5e5e5!important;box-shadow:none!important}
.version-tag,.product-version{color:#787878!important;border-color:#393939!important;background:#171717!important}
.showcase-hero{margin:clamp(34px,6vh,70px) 0 34px!important;max-width:650px}
.showcase-hero h2{font-size:clamp(40px,4.5vw,66px)!important;font-weight:720!important;letter-spacing:-.06em!important;line-height:1.09!important;color:#f5f5f5!important;text-shadow:none!important}
.showcase-hero h2 em,.welcome h1 em,.login-heading h2 span{background:none!important;-webkit-text-fill-color:#aeaeae!important;color:#aeaeae!important;font-style:normal}
.showcase-hero p{color:#a3a3a3!important;font-size:14px!important;line-height:1.75!important;max-width:450px!important}
.showcase-product{position:relative;z-index:2;width:100%;margin:auto 0 30px;background:#161616;border:1px solid #303030;border-radius:15px;overflow:hidden;box-shadow:0 15px 38px #0003}
.product-heading{display:flex;align-items:center;gap:9px;padding:14px 20px;border-bottom:1px solid #303030;font-size:10px;letter-spacing:.08em;color:#bbbbbb;font-weight:670}
.product-indicator{width:7px;height:7px;border-radius:50%;display:inline-block}
.product-version{margin-left:auto;letter-spacing:.1em;font-size:10px}
.product-main{padding:29px 26px 22px}
.product-label{font-size:10px;font-weight:650;letter-spacing:.13em;color:#8b8b8b;margin-bottom:12px}
.product-main strong{display:block;color:#fafafa;font-size:clamp(19px,2vw,27px);font-weight:620;letter-spacing:-.035em}
.product-main p{font-size:12px;line-height:1.7;color:#989898;max-width:440px;margin:9px 0 0}
.product-rows>div{display:flex;gap:18px;align-items:center;border-top:1px solid #2b2b2b;padding:15px 23px;color:#cecece;font-size:12px}
.product-num{font-size:10px;color:#858585;letter-spacing:.08em}.product-arrow{margin-left:auto;color:#aaa}
.showcase-foot{border-top:1px solid #303030!important;color:#999!important;padding-top:20px!important;gap:8px!important}.foot-symbol{color:#ddd!important}
.login-panel{background:#0d0d0d!important;box-shadow:none!important;padding:clamp(24px,4vw,58px)!important;align-items:center!important}
.login-card{max-width:425px!important;width:100%!important;background:transparent!important;border:0!important;border-radius:0!important;box-shadow:none!important;padding:0!important}
.login-brand{margin-bottom:clamp(42px,6vh,68px)!important}
.login-logo,.brand-icon,.welcome-logo,.assistant-avatar{background:#eaeaea!important;border:1px solid #fafafa!important;color:#101010!important;box-shadow:none!important;transform:none!important}
.login-heading h2{color:#f5f5f5!important;font-size:clamp(30px,3vw,42px)!important}.login-heading p{color:#a0a0a0!important}.login-brand p,.brand span{color:#858585!important}
.login-form label{color:#bcbcbc!important;letter-spacing:.035em!important}
.login-form input{background:#181818!important;color:#f2f2f2!important;border:1px solid #373737!important;border-radius:9px!important;box-shadow:none!important;height:53px!important}
.login-form input:focus{border-color:#b1b1b1!important;box-shadow:0 0 0 3px #ffffff13!important;outline:none!important}
.login-form input::placeholder{color:#747474!important}.password-toggle{color:#c8c8c8!important}
.login-button{border:1px solid #eee!important;border-radius:9px!important;background:#f5f5f5!important;color:#111!important;box-shadow:none!important;transition:background .15s ease,transform .15s ease!important}
.login-button:hover:not(:disabled){background:#dedede!important;transform:translateY(-1px)!important;box-shadow:none!important}
.login-security{color:#7e7e7e!important;border-top-color:#303030!important}.login-security span:last-child,.security-lock{color:#aaa!important}
.app{background:#090909!important}
.sidebar{background:#101010!important;border-right:1px solid #2d2d2d!important;box-shadow:none!important;max-width:85vw!important}
.sidebar-header{background:#101010!important}.brand strong{color:#efefef!important}
.new-chat{background:#ededed!important;color:#111!important;border:1px solid #f5f5f5!important;border-radius:9px!important;box-shadow:none!important;font-weight:740!important}
.new-chat:hover:not(:disabled){background:#d5d5d5!important;filter:none!important;box-shadow:none!important}
.history-label,.topbar-path,.topbar-version,.banner-overline,.welcome-eyebrow{color:#8c8c8c!important}
.history{scrollbar-color:#484848 transparent!important}.history-item{color:#a7a7a7!important;border:1px solid transparent!important;border-radius:9px!important;box-shadow:none!important}
.history-icon{color:#757575!important}.history-item:hover{background:#1d1d1d!important;color:#f0f0f0!important;border-color:#313131!important}
.history-item.active{background:#252525!important;color:#fafafa!important;border:1px solid #444!important;box-shadow:inset 2px 0 #ddd!important}
.sidebar-footer{background:#101010!important;border-top:1px solid #303030!important}.sidebar-status{color:#999!important}.status-dot,.badge-led{background:#a3b5a9!important;box-shadow:none!important}
.logout-button{background:#181818!important;color:#cfcfcf!important;border:1px solid #3b3b3b!important;border-radius:9px!important}.logout-button:hover{background:#242424!important}
.main{background:#0a0a0a!important;isolation:auto!important}
.topbar{background:#101010!important;border-bottom:1px solid #2a2a2a!important;box-shadow:none!important;backdrop-filter:none!important;height:75px!important}
.topbar-title strong{color:#f2f2f2!important}.topbar-title small{color:#898989!important}.topbar-path span{color:#bbb!important}
.topbar-badge{color:#cccccc!important;background:#1c1c1c!important;border:1px solid #383838!important;box-shadow:none!important}.topbar-initial{background:#282828!important;color:#eee!important;border:1px solid #424242!important}
.chat-area{background:#0a0a0a!important;scrollbar-color:#494949 transparent!important}
.welcome{max-width:820px!important}.welcome-logo{box-shadow:none!important}.welcome h1{color:#f5f5f5!important;font-size:clamp(38px,4.5vw,61px)!important;letter-spacing:-.055em!important;text-shadow:none!important}
.welcome p{color:#aaa!important}.welcome-version{color:#aaa!important;border:1px solid #383838!important}.welcome-capabilities span{background:#171717!important;border:1px solid #323232!important;color:#bdbdbd!important}.welcome-capabilities b,.suggestion-label span{color:#c9c9c9!important}
.suggestion-label{color:#929292!important}.suggestion{background:#171717!important;border:1px solid #323232!important;color:#d5d5d5!important;box-shadow:none!important;border-radius:12px!important;transition:background .15s,border-color .15s!important}
.suggestion:hover{background:#202020!important;border-color:#5a5a5a!important;color:#fff!important;transform:none!important;box-shadow:none!important}
.suggestion-icon{background:#252525!important;color:#e2e2e2!important}
.conversation-banner{background:#151515!important;border:1px solid #303030!important;border-radius:12px!important;box-shadow:none!important}.conversation-banner::after{display:none!important}.conversation-banner h2{color:#eee!important}.conversation-banner p{color:#999!important}.banner-glow{color:#a0a0a0!important;text-shadow:none!important}
.message-name{color:#dedede!important}.message-text{color:#e6e6e6!important}.message-content{color:#e6e6e6!important}
.assistant-message .message-text{background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;max-width:unset!important}
.user-row .user-message{background:#242424!important;color:#eee!important;border:1px solid #3a3a3a!important;border-radius:15px 15px 4px 15px!important;box-shadow:none!important}
.chart-wrapper,.table-wrapper{background:#151515!important;border:1px solid #353535!important;border-radius:13px!important;box-shadow:none!important}
.chart-wrapper:hover{border-color:#4d4d4d!important}.result-card-header{background:#191919!important;border-bottom:1px solid #333!important;color:#e6e6e6!important}.result-eyebrow{color:#cecece!important}.result-records{background:#252525!important;color:#ccc!important;border:1px solid #414141!important}
.table-wrapper th{background:#202020!important;color:#bbb!important;border-bottom:1px solid #383838!important}.table-wrapper td{color:#ddd!important;border-color:#2d2d2d!important}.table-wrapper tbody tr:first-child td{background:#222!important}.table-wrapper tbody tr:hover td{background:#282828!important}
.download-button{background:#222!important;color:#e2e2e2!important;border:1px solid #393939!important;box-shadow:none!important}.download-button:hover{background:#303030!important;box-shadow:none!important}
.contribution-panel{background:#171717!important;border-color:#3a3a3a!important}.contribution-heading h3{color:#eaeaea!important}.contribution-track{background:#303030!important}.contribution-fill{background:#bfbfbf!important}.contribution-fill.negative{background:#a16c6c!important}
.input-section{background:#101010!important;border-top:1px solid #303030!important;box-shadow:none!important;z-index:2}
.input-box{background:#1b1b1b!important;border:1px solid #424242!important;border-radius:13px!important;box-shadow:none!important}.input-box:focus-within{border-color:#898989!important;box-shadow:0 0 0 3px #ffffff10!important}
.send-button{background:#f0f0f0!important;color:#151515!important;border-radius:9px!important;box-shadow:none!important}.input-hint{color:#818181!important}
@media(max-width:740px){.login-shell{grid-template-columns:1fr!important;min-height:0!important}.login-showcase{min-height:0!important;padding:30px 26px!important;border-right:0!important;border-bottom:1px solid #303030!important}.showcase-hero{margin:24px 0!important}.showcase-hero h2{font-size:36px!important}.showcase-product,.showcase-foot{display:none!important}.login-panel{padding:30px 24px 39px!important}.login-brand{margin-bottom:32px!important}.topbar{height:70px!important}.welcome h1{font-size:39px!important}}
@media(prefers-reduced-motion:reduce){.login-page *, .app *{animation-duration:.01ms!important;transition-duration:.01ms!important}}


/* A custom vector identity: an architectural B with a separate spine. */
.login-logo,.brand-icon,.welcome-logo,.assistant-avatar{
  background:#f5f5f5!important;
  border:1px solid #fdfdfd!important;
  border-radius:14px!important;
  color:#0b0b0b!important;
  display:grid!important;
  place-items:center!important;
  overflow:hidden;
}
.bundle-mark-svg {display:block;width:68%;height:68%;max-width:100%;overflow:visible}
.welcome-logo .bundle-mark-svg {width:63%;height:63%}
.assistant-avatar .bundle-mark-svg{width:68%;height:68%}
/* The badge is a decoration, not an interactive control. */


/* NOIR / ATMOSPHERE: premium black, frosted graphite, editorial silver. */
.login-page,.app { isolation:isolate; }
.noir-atmosphere { position:absolute; inset:0; overflow:hidden; z-index:0; pointer-events:none; background:radial-gradient(ellipse at 75% 20%,rgba(170,189,212,.095),transparent 35%),radial-gradient(ellipse at 8% 85%,rgba(105,128,157,.095),transparent 38%),linear-gradient(135deg,#08090c,#0e1014 45%,#07080a); }
.noir-atmosphere-grid { position:absolute; inset:0; background-image:linear-gradient(rgba(227,234,245,.038) 1px,transparent 1px),linear-gradient(90deg,rgba(227,234,245,.038) 1px,transparent 1px);background-size:68px 68px;mask-image:linear-gradient(110deg,transparent,#000 40%,#000 65%,transparent);opacity:.65;transform:perspective(700px) rotateX(6deg) scale(1.15); }
.noir-orbit { position:absolute;border:1px solid rgba(220,233,251,.15);border-radius:50%;box-shadow:inset 0 0 40px rgba(210,224,248,.025),0 0 70px rgba(160,190,235,.04); }
.noir-orbit-one { width:min(58vw,740px); aspect-ratio:1;top:9%;left:13%;transform:rotate(-22deg); }
.noir-orbit-one::before,.noir-orbit-two::before {content:'';position:absolute;inset:12%;border:1px solid rgba(222,235,251,.095);border-radius:50%; }
.noir-orbit-two {width:min(36vw,470px);aspect-ratio:1;right:-9%;bottom:-14%;border-style:dashed;border-color:rgba(225,232,244,.13);}
.noir-light {position:absolute;inset:0;background:radial-gradient(circle at 65% 43%,rgba(255,255,255,.08) 0 1px,transparent 2px),radial-gradient(circle at 24% 30%,rgba(255,255,255,.25) 0 1px,transparent 3px),radial-gradient(circle at 48% 68%,rgba(255,255,255,.18) 0 2px,transparent 4px);background-size:240px 190px,310px 250px,410px 320px;opacity:.55;}
.login-page > .login-shell {position:relative;z-index:1;box-shadow:0 32px 110px #000c,0 0 0 1px #dceaff20!important;}
.login-page .login-showcase {background:linear-gradient(150deg,rgba(24,26,31,.86),rgba(9,10,13,.94))!important;}
.login-page .login-showcase::after {display:block!important;content:'';position:absolute;inset:0;pointer-events:none;background:radial-gradient(circle at 65% 65%,rgba(220,228,240,.08),transparent 44%);}
.login-page .login-panel {background:linear-gradient(145deg,rgba(21,22,25,.75),rgba(8,9,11,.92))!important;}
.login-page .login-card {border-radius:26px!important;}
.app .sidebar,.app .main {position:relative;z-index:1;}
.app .main {background:radial-gradient(circle at 94% 6%,rgba(211,220,230,.055),transparent 36%),transparent!important;}
.app .chat-area {position:relative;z-index:1;}
.app .topbar,.app .input-section {position:relative;z-index:2;backdrop-filter:blur(18px);}
.app .topbar {background:rgba(14,15,18,.8)!important;}
.app .input-section {background:linear-gradient(0deg,#090a0cf2,#090a0cb5)!important;}
.app .sidebar {background:linear-gradient(165deg,rgba(19,20,24,.96),rgba(10,11,14,.98))!important;}
.app .history-item.active {background:linear-gradient(105deg,#30343a,#18191c)!important;border-color:#a6b2c154!important;}
.app .new-chat {box-shadow:0 10px 30px #0008,0 0 20px #ffffff11!important;}
.app .conversation-banner,.app .message-content.assistant-message {backdrop-filter:blur(14px);}
.history-search-label {display:flex;align-items:center;gap:9px;margin:10px 12px 17px;padding:0 12px;border:1px solid #42464e;background:#1b1d21;border-radius:11px;color:#a7adb8;min-height:41px;}
.history-search-label:focus-within {border-color:#9da5b4;box-shadow:0 0 0 3px #e5ebf010;}
.history-search-label input {flex:1;min-width:0;background:transparent;border:0;outline:0;color:#ededf1;font:inherit;font-size:12px;padding:10px 0;}
.history-search-label input::placeholder {color:#9699a0;}
.transcript-action {background:#202226;color:#d6d9df;border:1px solid #50535b;border-radius:9px;padding:9px 12px;font-size:11px;cursor:pointer;white-space:nowrap;}
.transcript-action:hover:not(:disabled),.reply-actions button:hover {background:#30333a;border-color:#9a9da5;}
.transcript-action:disabled {opacity:.45;cursor:not-allowed;}
.reply-actions {display:flex;gap:9px;margin-top:9px;}
.reply-actions button {cursor:pointer;background:#202226;color:#bec6d2;border:1px solid #3d424b;border-radius:8px;padding:6px 9px;font-size:11px;}
.export-notice {color:#eee;font-size:12px;margin:2px 0 8px;text-align:center;}
.sr-only{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;}
@media(max-width:750px){.transcript-action{padding:8px;font-size:10px}.noir-orbit-one{width:85vw;left:22%;top:25%}.history-search-label{margin:8px 10px 12px}}
@media(prefers-reduced-motion:no-preference){.noir-orbit-one{animation:noir-drift 35s ease-in-out infinite alternate}.noir-orbit-two{animation:noir-drift 42s ease-in-out infinite alternate-reverse}@keyframes noir-drift{from{transform:translate3d(0,0,0) rotate(-15deg)}to{transform:translate3d(22px,-17px,0) rotate(10deg)}}}



/* BUNDLE NOIR / ATELIER — intentional dark-space depth without external assets. */
:global(body) { background:#050608; }
.login-page,.app{--noir-cyan:#baf6eb;--noir-silver:#edf1f6;--noir-ice:#c5d0dc;}
.login-page{background:radial-gradient(ellipse at 5% 8%,#20242d 0,transparent 45%),radial-gradient(ellipse at 95% 90%,#1b2630 0,transparent 44%),#07080a!important;}
.login-page .noir-atmosphere{background:radial-gradient(ellipse at 70% 12%,rgba(116,160,178,.11),transparent 44%),radial-gradient(ellipse at 16% 76%,rgba(173,181,198,.09),transparent 49%),#050608;}
.login-page .noir-atmosphere-grid,.app .noir-atmosphere-grid{opacity:.78;background-size:74px 74px;mask-image:linear-gradient(130deg,transparent 3%,#000 40%,#000 70%,transparent 100%);}
.login-page .noir-orbit,.app .noir-orbit{border-color:rgba(205,224,230,.21);}
.login-page .login-shell{border:1px solid #75818d55!important;box-shadow:0 45px 120px #000e,0 0 75px #a6b8bd13,inset 0 1px 0 #ffffff17!important;}
.login-page .login-showcase{isolation:isolate;background:radial-gradient(circle at 75% 55%,#29343c80,transparent 53%),linear-gradient(145deg,#181b20,#090b0e)!important;}
.login-page .login-showcase::after{background:linear-gradient(145deg,#ffffff0a,transparent 31%),radial-gradient(circle at 78% 55%,#9bb9b712,transparent 40%)!important;}
.login-page .showcase-hero{z-index:3;max-width:470px;margin-top:49px!important;}
.login-page .showcase-hero h2{text-shadow:0 4px 36px #000!important;}
.login-page .showcase-hero h2 em,.welcome h1 em{background:linear-gradient(110deg,#f4f7fa,#afbfc8 52%,#89bfb6)!important;-webkit-background-clip:text!important;background-clip:text!important;-webkit-text-fill-color:transparent!important;color:#c5d2d5!important;}
.noir-instrument{position:absolute;z-index:1;width:min(88%,485px);aspect-ratio:1;right:-16%;top:16%;pointer-events:none;opacity:.9;filter:drop-shadow(0 0 42px #96b8bb19);}
.instrument-arc{position:absolute;border-radius:50%;inset:4%;border:1px solid #a1b8c568;box-shadow:inset 0 0 40px #adcad111,0 0 30px #85aeb414;background:repeating-conic-gradient(from 0deg,transparent 0deg 12deg,#c9e0e413 12.2deg 12.5deg,transparent 13deg 25deg);}
.instrument-arc-outer::after{content:'';position:absolute;inset:-15px;border-radius:50%;border:1px dashed #8b9ba433;}
.instrument-arc-middle{inset:14%;border:1px solid #dceaf177;background:repeating-conic-gradient(from 13deg,#b1c5cc1a 0deg 2deg,transparent 2deg 35deg);transform:rotate(15deg);}
.instrument-arc-inner{inset:27%;border:1px solid #e0e7ec8a;background:radial-gradient(circle at 45% 37%,#a9c9c936,#111921 40%,#030506 80%);box-shadow:0 0 45px #b5dcda1a,inset 0 0 35px #c6dddd21;}
.instrument-crosshair{position:absolute;inset:0;background:linear-gradient(90deg,transparent 49.9%,#c8f0ef32 50%,transparent 50.1%),linear-gradient(transparent 49.9%,#c8f0ef32 50%,transparent 50.1%);mask-image:radial-gradient(circle,#000 0 56%,transparent 69%);}
.instrument-core{position:absolute;inset:34%;display:flex;flex-direction:column;align-items:center;justify-content:center;border:1px solid #f0ffff85;border-radius:29%;background:linear-gradient(155deg,#dadee6,#a0aeb7 45%,#141a20 47%,#12161d);box-shadow:0 0 26px #bbf1ed33,0 0 68px #baf9ef1c,inset 0 0 24px #dceef018;transform:rotate(-9deg);}
.instrument-glyph{font-size:clamp(35px,4vw,58px);line-height:1;font-weight:950;color:#f7ffff;text-shadow:0 2px 18px #bcd5d555;letter-spacing:-.08em;transform:rotate(9deg);}
.instrument-core-caption{position:absolute;bottom:-33px;white-space:nowrap;color:#c7d4d6;font-size:8px;letter-spacing:.23em;font-weight:700;}
.instrument-coordinate{position:absolute;white-space:nowrap;color:#b6c6cb;font-size:8px;font-weight:750;letter-spacing:.2em;text-shadow:0 2px 10px #000;}
.instrument-coordinate-top{right:9%;top:11%;}.instrument-coordinate-bottom{left:-9%;bottom:12%;}
.login-page .showcase-product{position:relative;z-index:3;background:#15181beb!important;border-color:#9ba7b44b!important;box-shadow:0 22px 44px #0009, inset 0 1px 0 #ffffff0f;max-width:490px;margin-top:48px!important;}
.login-page .login-panel{background:linear-gradient(160deg,#14171ad6,#070809f2)!important;box-shadow:inset 1px 0 #9aadb524;}
.login-page .login-form input{background:#12161a!important;border-color:#545d66!important;}
.login-page .login-form input:focus{border-color:#b4dedb!important;box-shadow:0 0 0 4px #b3e8e516!important;}
.login-page .login-button{background:linear-gradient(103deg,#f3f4f6,#b9c9d0 62%,#91b9b5)!important;color:#10151a!important;border-color:#d2e8e4!important;box-shadow:0 14px 46px #a6d2c61b!important;}
.login-page .login-button:hover:not(:disabled){box-shadow:0 17px 55px #d7ffff35!important;}
/* A recognizable emblem: split-spine monogram, dark metallic halo. */
.login-logo,.brand-icon,.welcome-logo,.assistant-avatar{position:relative;border:1px solid #d4e0e0!important;background:linear-gradient(145deg,#f9fbfd,#a5bdbe)!important;box-shadow:0 0 0 5px #cededf0a,0 9px 35px #bdd8d823!important;}
.login-logo::after,.brand-icon::after,.welcome-logo::after{content:'';position:absolute;inset:-1px;border-radius:inherit;pointer-events:none;box-shadow:inset 0 1px #ffffffbf;}
/* Layered studio lighting for the AI workspace. */
.app{background:#06080b!important;}
.app .noir-atmosphere{background:radial-gradient(ellipse at 75% 10%,#55758125,transparent 42%),radial-gradient(ellipse at 16% 90%,#7e9da318,transparent 45%),linear-gradient(150deg,#0b0e12,#050608)!important;}
.workspace-aura{position:absolute;right:-4%;top:13%;width:min(64vw,940px);aspect-ratio:1;opacity:.24;filter:drop-shadow(0 0 48px #b4cdd72a);}
.workspace-aura span{position:absolute;inset:8%;border:1px solid #d9ebf054;border-radius:50%;transform:rotate(-28deg) scaleY(.6);}
.workspace-aura span:nth-child(2){transform:rotate(47deg) scaleY(.7);inset:17%;border-style:dashed;border-color:#cbdae568;}
.workspace-aura span:nth-child(3){inset:30%;border-color:#deeff098;box-shadow:0 0 100px #90bcc628,inset 0 0 85px #8db6ba20;}
.app .sidebar{border-right-color:#59636d55!important;box-shadow:8px 0 48px #0007!important;}
.app .main{background:radial-gradient(ellipse at 92% 15%,#7a9a9b13,transparent 42%),transparent!important;}
.app .topbar{border-bottom-color:#899da132!important;box-shadow:inset 0 1px #c6e4e30c;}
.app .new-chat{background:linear-gradient(110deg,#f0f2f3,#b9ced0)!important;color:#0c1116!important;border:1px solid #e9f7f5!important;box-shadow:0 5px 30px #accbcd24!important;}
.app .history-item.active{background:linear-gradient(100deg,#313e41,#181d22)!important;border-color:#c3d2d64c!important;}
.app .welcome-logo{box-shadow:0 0 0 12px #d4eeee0a,0 0 85px #b8d7d325!important;}
.app .welcome h1{text-shadow:0 4px 44px #0008!important;}
.app .suggestion,.app .conversation-banner,.app .result-card-header{border-color:#9eacad33!important;box-shadow:inset 0 1px 0 #eef7f70a,0 16px 50px #0003;}
.app .suggestion:hover:not(:disabled){border-color:#a3d2d0aa!important;box-shadow:0 5px 34px #adc4ca19!important;transform:translateY(-2px);}
.app .input-box{border-color:#a0aeb65c!important;box-shadow:0 0 0 1px #dce6e50b,0 0 42px #c3e0e013!important;}
.app .input-box:focus-within{border-color:#c6e7e1!important;box-shadow:0 0 0 3px #e7f6f614,0 0 45px #c1e9dc1f!important;}
/* legible secondary labels, rather than low-contrast greys */
.login-page .showcase-hero p,.login-page .login-heading p,.app .welcome p,.app .topbar-title small{color:#bac3ca!important;}
@media(max-width:960px){.noir-instrument{right:-33%;top:22%;opacity:.45}.login-page .showcase-product{margin-top:25px!important;}.workspace-aura{width:90vw;right:-28%}}
@media(max-width:700px){.noir-instrument{width:68vw;right:-40%;top:4%;opacity:.19}.login-page .showcase-hero{margin-top:23px!important}.workspace-aura{opacity:.12}.login-page .login-shell{width:100%!important}.login-page .login-panel{box-shadow:none}}
@media(prefers-reduced-motion:no-preference){.instrument-arc-outer{animation:noir-instrument-turn 80s linear infinite}.instrument-arc-middle{animation:noir-instrument-turn 58s linear infinite reverse}.workspace-aura span:first-child{animation:noir-aura-turn 95s linear infinite}@keyframes noir-instrument-turn{to{transform:rotate(360deg)}}@keyframes noir-aura-turn{to{transform:rotate(332deg) scaleY(.6)}}}


/* ===========================================================
   BUNDLE / RESPONSIVE VIEWPORT FIT
   Desktop: no page-level scrolling. Scroll only long chat/history.
   =========================================================== */
:global(html),:global(body){margin:0;min-height:100%;}
:global(*){box-sizing:border-box;}
.login-page{
  height:100dvh!important;
  min-height:0!important;
  padding:clamp(10px,1.6vh,22px)!important;
  overflow:hidden!important;
  display:flex!important;
}
.login-page .login-shell{
  width:min(1220px,100%)!important;
  height:min(830px,calc(100dvh - clamp(20px,3.2vh,44px)))!important;
  min-height:0!important;
  max-height:100%!important;
  grid-template-columns:minmax(0,1.08fr) minmax(0,.92fr)!important;
}
.login-page .login-showcase{
  min-height:0!important;
  height:100%!important;
  padding:clamp(18px,2.8vh,35px) clamp(24px,2.8vw,46px)!important;
  overflow:hidden!important;
}
.login-page .showcase-hero{
  margin:clamp(12px,2.5vh,32px) 0 clamp(9px,1.6vh,20px)!important;
}
.login-page .showcase-hero h2{
  font-size:clamp(31px,min(3.7vw,5.4vh),55px)!important;
  line-height:1.06!important;
  margin:clamp(8px,1.4vh,14px) 0!important;
}
.login-page .showcase-hero p{font-size:clamp(11px,1.4vh,14px)!important;line-height:1.55!important;}
.login-page .showcase-product{
  margin-top:clamp(9px,1.7vh,20px)!important;
  margin-bottom:clamp(7px,1.4vh,16px)!important;
}
.login-page .showcase-foot{padding-top:clamp(9px,1.3vh,16px)!important;gap:9px!important;}
.login-page .login-panel{
  height:100%;min-height:0!important;
  padding:clamp(18px,3vh,35px) clamp(24px,3.6vw,48px)!important;
  overflow-y:auto;
  scrollbar-width:thin;
}
.login-page .login-brand{margin-bottom:clamp(16px,3vh,36px)!important;}
.login-page .login-heading{margin-bottom:clamp(13px,2.4vh,24px)!important;}
.login-page .login-heading h2{font-size:clamp(27px,3.6vh,38px)!important;}
.login-page .login-heading p{line-height:1.5!important;}
.login-page .login-form{gap:clamp(11px,1.8vh,18px)!important;}
.login-page .login-form input{height:clamp(42px,5.6vh,51px)!important;}
.login-page .login-button{height:clamp(43px,5.8vh,53px)!important;}
.login-page .login-security{margin-top:clamp(16px,2.8vh,29px)!important;padding-top:14px!important;}
.app{height:100dvh!important;min-height:0!important;max-height:100dvh!important;overflow:hidden!important;}
.app .main{min-height:0!important;min-width:0!important;overflow:hidden!important;}
.app .sidebar{height:100%;min-height:0!important;}
.app .history{min-height:0!important;overflow-y:auto!important;overscroll-behavior:contain;}
.app .topbar{height:clamp(56px,8vh,78px)!important;min-height:56px;flex-shrink:0!important;}
.app .chat-area{min-height:0!important;overflow-y:auto!important;overscroll-behavior:contain;}
.app .input-section{flex-shrink:0!important;padding-top:clamp(9px,1.5vh,14px)!important;padding-bottom:clamp(8px,1.4vh,15px)!important;}
.app .input-box{min-height:clamp(48px,6.8vh,62px)!important;}
.app .welcome{
  min-height:0!important;
  max-width:900px;
  margin:auto!important;
  padding:clamp(7px,1.8vh,22px) 5px!important;
}
.app .welcome-logo{width:clamp(47px,7.5vh,75px)!important;height:clamp(47px,7.5vh,75px)!important;margin-bottom:clamp(9px,1.5vh,17px)!important;}
.app .welcome h1{
  font-size:clamp(32px, min(4.0vw, 6vh), 57px)!important;
  margin:clamp(8px,1.5vh,14px) auto!important;
  line-height:1.04!important;
}
.app .welcome p{font-size:clamp(11px,1.5vh,14px)!important;line-height:1.5!important;margin-bottom:clamp(14px,2vh,25px)!important;}
.app .welcome-capabilities{margin:0 auto clamp(12px,2vh,22px)!important;gap:8px!important;}
.app .suggestions{gap:clamp(7px,1vh,12px)!important;}
.app .suggestion{min-height:clamp(54px,8vh,82px)!important;padding:clamp(10px,1.5vh,15px)!important;}
/* Preserve a usable scrolling form and chat when the viewport is extremely short. */
@media(max-height:740px) and (min-width:741px){
  .login-page .showcase-foot{display:none!important;}
  .login-page .showcase-product{margin-top:8px!important;}
  .login-page .showcase-hero{margin-top:9px!important;}
  .login-page .noir-instrument{opacity:.35!important;}
  .app .welcome-eyebrow{margin-bottom:6px!important;}
  .app .welcome-capabilities{margin-bottom:10px!important;}
  .app .suggestion-label{margin-bottom:7px!important;}
}
/* On phones and narrow tablet layouts, content must remain reachable. */
@media(max-width:740px){
  .login-page{height:auto!important;min-height:100dvh!important;overflow-y:auto!important;display:block!important;padding:10px!important;}
  .login-page .login-shell{height:auto!important;max-height:none!important;min-height:0!important;display:grid!important;grid-template-columns:minmax(0,1fr)!important;}
  .login-page .login-showcase{height:auto!important;min-height:0!important;padding:22px!important;}
  .login-page .login-panel{height:auto!important;max-height:none!important;overflow:visible!important;padding:26px 22px!important;}
  .login-page .showcase-product,.login-page .showcase-foot{display:none!important;}
  .login-page .showcase-hero h2{font-size:clamp(31px,7.5vw,43px)!important;}
  .app .chat-area{padding:12px!important;}
  .app .welcome h1{font-size:clamp(29px,7vw,42px)!important;}
  .app .suggestions{grid-template-columns:1fr!important;}
}


/* =====================================================
   BUNDLE NOIR · OPTIONAL POLISH (CSS ONLY)
   Adds depth and accessible interaction feedback.
   No changes to business logic, HTML, routing or sizing.
   ===================================================== */
.login-page,
.app {
  --noir-silver: #c5d6d7;
  --noir-glint: rgba(199, 235, 232, .16);
  --noir-edge: rgba(208, 227, 231, .13);
}
/* Brushed graphite ambience: deliberately low contrast to protect readability. */
.login-page {
  background-image:
    radial-gradient(ellipse 52% 38% at 11% 17%, rgba(166,208,211,.075), transparent 75%),
    radial-gradient(ellipse 43% 57% at 91% 76%, rgba(115,149,169,.08), transparent 78%),
    linear-gradient(140deg, #08090b, #0d1012 50%, #090a0c) !important;
}
.app {
  background-image:
    radial-gradient(ellipse 35% 54% at 89% 44%, rgba(133,183,190,.06), transparent 80%),
    radial-gradient(ellipse 39% 44% at 29% 86%, rgba(104,125,144,.045), transparent 80%),
    linear-gradient(145deg, #08090b, #0c0f11 58%, #090a0c) !important;
}
/* Keep decoration behind the real content, never across input controls. */
.login-shell,
.login-panel,
.login-showcase {
  position: relative;
  isolation: isolate;
}
.login-shell {
  box-shadow: 0 36px 115px rgba(0,0,0,.52), 0 0 0 1px rgba(225,244,245,.035), 0 0 75px rgba(153,199,199,.035);
}
.login-shell::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background: linear-gradient(124deg, rgba(229,255,255,.065), transparent 25%, transparent 72%, rgba(190,223,226,.035));
  z-index: 0;
}
.login-showcase::before {
  content: '';
  position: absolute;
  width: min(33vw, 490px);
  aspect-ratio: 1;
  border: 1px solid rgba(205,232,236,.08);
  border-radius: 50%;
  right: -15%;
  top: 17%;
  pointer-events: none;
  box-shadow: 0 0 0 46px rgba(208,236,240,.015), 0 0 0 92px rgba(208,236,240,.008);
  opacity: .75;
  z-index: -1;
}
/* Microinteractions do not change dimensions, click targets or data. */
.login-button,
.suggestion,
.input-box,
.login-panel input {
  transition: box-shadow .22s ease, border-color .22s ease, filter .22s ease, transform .22s ease;
}
.login-button:hover,
.suggestion:hover {
  filter: brightness(1.07);
  transform: translateY(-2px);
}
.suggestion:hover {
  box-shadow: 0 10px 34px rgba(0,0,0,.2), inset 0 0 0 1px rgba(214,241,239,.085);
}
.login-panel input:focus-visible,
.input-box:focus-within {
  outline: 2px solid rgba(188,237,235,.68);
  outline-offset: 2px;
  box-shadow: 0 0 0 5px rgba(181,232,231,.07);
}
/* Add modest depth to the existing sidebar and header, not more components. */
.sidebar {
  box-shadow: 12px 0 45px rgba(0,0,0,.12);
}
.topbar {
  box-shadow: 0 1px 0 rgba(225,244,245,.045), 0 12px 38px rgba(0,0,0,.1);
}
/* No new scrollbars, focus traps, motion on mobile or reduced-motion devices. */
@media (max-width: 740px) {
  .login-showcase::before { display: none; }
  .login-button:hover,
  .suggestion:hover { transform: none; }
}
@media (prefers-reduced-motion: reduce) {
  .login-button,
  .suggestion,
  .input-box,
  .login-panel input { transition: none; }
}



/* =========================================================
   RBAC / ROLE-AWARE WORKSPACE
   Additive only: existing Noir layout and interactions remain.
   ========================================================= */

.account-summary {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  padding: 10px 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.012));
}

.account-avatar {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.055);
  color: rgba(255, 255, 255, 0.94);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.account-details {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.account-details strong {
  overflow: hidden;
  color: rgba(255, 255, 255, 0.9);
  font-size: 12px;
  font-weight: 650;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.account-details span {
  color: rgba(255, 255, 255, 0.38);
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.14em;
}

.role-chip {
  padding: 5px 7px;
  border: 1px solid rgba(123, 231, 211, 0.22);
  border-radius: 999px;
  background: rgba(123, 231, 211, 0.06);
  color: rgba(173, 244, 231, 0.8);
  font-size: 7px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.role-chip.viewer-role,
.topbar-badge.viewer-badge {
  border-color: rgba(255, 255, 255, 0.11);
  background: rgba(255, 255, 255, 0.035);
  color: rgba(255, 255, 255, 0.56);
}

.viewer-notice {
  width: min(900px, calc(100% - 32px));
  margin: 0 auto 10px;
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 12px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 13px;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.012));
  color: rgba(255, 255, 255, 0.58);
}

.viewer-notice-icon {
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  display: grid;
  place-items: center;
  border-radius: 9px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: rgba(255, 255, 255, 0.68);
}

.viewer-notice > div {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.viewer-notice strong {
  color: rgba(255, 255, 255, 0.82);
  font-size: 11px;
  font-weight: 700;
}

.viewer-notice span:not(.viewer-notice-icon) {
  font-size: 10px;
  line-height: 1.45;
}

.input-box textarea:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.suggestion:disabled {
  cursor: not-allowed;
}

@media (max-width: 720px) {
  .account-summary {
    grid-template-columns: 32px minmax(0, 1fr) auto;
  }

  .viewer-notice {
    width: calc(100% - 20px);
  }
}



/* =========================================================
   RBAC STAGE 4 — ADMIN USER MANAGEMENT
   ========================================================= */

.workspace-switcher {
  display: grid;
  gap: 6px;
  margin: 0 0 12px;
}

.workspace-switcher button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 9px 10px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  color: rgba(255, 255, 255, 0.46);
  cursor: pointer;
  text-align: left;
  font-size: 10px;
  font-weight: 650;
  transition:
    background 160ms ease,
    border-color 160ms ease,
    color 160ms ease;
}

.workspace-switcher button:hover,
.workspace-switcher button.active {
  border-color: rgba(255, 255, 255, 0.09);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.9);
}

.workspace-switcher button span {
  width: 18px;
  color: rgba(151, 238, 221, 0.72);
  text-align: center;
}

.admin-workspace {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding: 28px clamp(18px, 3vw, 42px) 48px;
  background:
    radial-gradient(circle at 82% 0%, rgba(110, 232, 208, 0.045), transparent 30%),
    radial-gradient(circle at 12% 24%, rgba(255, 255, 255, 0.025), transparent 32%);
}

.admin-hero {
  max-width: 1180px;
  margin: 0 auto 20px;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
}

.admin-overline,
.admin-card-heading span {
  display: block;
  color: rgba(152, 238, 221, 0.62);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.16em;
}

.admin-hero h1 {
  margin: 7px 0 6px;
  color: rgba(255, 255, 255, 0.96);
  font-size: clamp(28px, 3vw, 42px);
  font-weight: 620;
  letter-spacing: -0.04em;
}

.admin-hero p {
  margin: 0;
  color: rgba(255, 255, 255, 0.48);
  font-size: 12px;
  line-height: 1.6;
}

.admin-refresh,
.admin-row-actions button,
.admin-reset-panel > button {
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 9px;
  background: rgba(255, 255, 255, 0.035);
  color: rgba(255, 255, 255, 0.68);
  cursor: pointer;
  font-size: 10px;
  font-weight: 650;
}

.admin-refresh:hover:not(:disabled),
.admin-row-actions button:hover:not(:disabled),
.admin-reset-panel > button:hover:not(:disabled) {
  border-color: rgba(151, 238, 221, 0.23);
  background: rgba(151, 238, 221, 0.055);
  color: rgba(255, 255, 255, 0.92);
}

.admin-refresh:disabled,
.admin-row-actions button:disabled,
.admin-reset-panel > button:disabled {
  cursor: not-allowed;
  opacity: 0.42;
}

.admin-alert {
  max-width: 1180px;
  margin: 0 auto 14px;
  padding: 10px 13px;
  border-radius: 10px;
  font-size: 11px;
}

.admin-alert-error {
  border: 1px solid rgba(255, 115, 115, 0.2);
  background: rgba(255, 80, 80, 0.05);
  color: rgba(255, 180, 180, 0.85);
}

.admin-alert-success {
  border: 1px solid rgba(151, 238, 221, 0.18);
  background: rgba(151, 238, 221, 0.045);
  color: rgba(183, 245, 232, 0.8);
}

.admin-grid {
  max-width: 1180px;
  margin: 0 auto 18px;
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(280px, 0.75fr);
  gap: 14px;
}

.admin-card {
  border: 1px solid rgba(255, 255, 255, 0.075);
  border-radius: 16px;
  background:
    linear-gradient(145deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0.012)),
    rgba(6, 8, 9, 0.9);
  box-shadow:
    0 18px 50px rgba(0, 0, 0, 0.2),
    inset 0 1px 0 rgba(255, 255, 255, 0.025);
}

.admin-create-card,
.admin-summary-card {
  padding: 18px;
}

.admin-card-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 16px;
}

.admin-card-heading h2 {
  margin: 5px 0 0;
  color: rgba(255, 255, 255, 0.9);
  font-size: 16px;
  font-weight: 650;
}

.admin-card-icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.025);
  color: rgba(151, 238, 221, 0.7);
}

.admin-create-form {
  display: grid;
  grid-template-columns: 1fr 1fr 150px auto;
  align-items: end;
  gap: 10px;
}

.admin-create-form label,
.admin-reset-panel label,
.admin-inline-field {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.admin-create-form label > span,
.admin-reset-panel label > span,
.admin-inline-field > span {
  color: rgba(255, 255, 255, 0.4);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.admin-create-form input,
.admin-create-form select,
.admin-inline-field select,
.admin-reset-panel input {
  width: 100%;
  min-height: 38px;
  border: 1px solid rgba(255, 255, 255, 0.085);
  border-radius: 9px;
  outline: none;
  background: rgba(0, 0, 0, 0.28);
  color: rgba(255, 255, 255, 0.86);
  padding: 0 11px;
  font-size: 11px;
}

.admin-create-form input:focus,
.admin-create-form select:focus,
.admin-inline-field select:focus,
.admin-reset-panel input:focus {
  border-color: rgba(151, 238, 221, 0.3);
  box-shadow: 0 0 0 3px rgba(151, 238, 221, 0.04);
}

.admin-create-form option,
.admin-inline-field option {
  background: #0c0e0f;
  color: #f4f4f4;
}

.admin-primary-action {
  min-height: 38px;
  padding: 0 15px;
  border: 1px solid rgba(179, 246, 233, 0.28);
  border-radius: 9px;
  background:
    linear-gradient(180deg, rgba(180, 247, 233, 0.15), rgba(118, 222, 201, 0.08));
  color: rgba(224, 255, 249, 0.92);
  cursor: pointer;
  font-size: 10px;
  font-weight: 750;
}

.admin-primary-action:disabled {
  cursor: not-allowed;
  opacity: 0.45;
}

.admin-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.admin-metrics div {
  padding: 13px;
  border: 1px solid rgba(255, 255, 255, 0.055);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.018);
}

.admin-metrics strong {
  display: block;
  color: rgba(255, 255, 255, 0.92);
  font-size: 20px;
  font-weight: 620;
}

.admin-metrics span {
  color: rgba(255, 255, 255, 0.38);
  font-size: 9px;
}

.admin-security-note {
  margin: 14px 0 0;
  color: rgba(255, 255, 255, 0.36);
  font-size: 9px;
  line-height: 1.55;
}

.admin-users-card {
  max-width: 1180px;
  margin: 0 auto;
  overflow: hidden;
}

.admin-users-heading {
  margin: 0;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.admin-user-count {
  color: rgba(255, 255, 255, 0.28) !important;
}

.admin-user-list {
  display: grid;
}

.admin-user-row {
  display: grid;
  grid-template-columns: minmax(180px, 1.5fr) minmax(130px, 0.8fr) 110px auto;
  align-items: center;
  gap: 14px;
  padding: 13px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.admin-user-row:last-child {
  border-bottom: 0;
}

.admin-user-row:hover {
  background: rgba(255, 255, 255, 0.018);
}

.admin-user-identity {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 10px;
}

.admin-user-avatar {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  display: grid;
  place-items: center;
  border: 1px solid rgba(255, 255, 255, 0.085);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.035);
  color: rgba(255, 255, 255, 0.82);
  font-size: 11px;
  font-weight: 800;
}

.admin-user-identity > div:last-child {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.admin-user-identity strong {
  overflow: hidden;
  color: rgba(255, 255, 255, 0.84);
  font-size: 11px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.admin-user-identity span {
  color: rgba(255, 255, 255, 0.32);
  font-size: 8px;
}

.admin-status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: rgba(162, 239, 224, 0.7);
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.admin-status-pill i {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(123, 231, 211, 0.84);
  box-shadow: 0 0 9px rgba(123, 231, 211, 0.3);
}

.admin-status-pill.inactive {
  color: rgba(255, 255, 255, 0.34);
}

.admin-status-pill.inactive i {
  background: rgba(255, 255, 255, 0.25);
  box-shadow: none;
}

.admin-row-actions {
  display: flex;
  justify-content: flex-end;
  gap: 7px;
}

.admin-reset-panel {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: minmax(220px, 1fr) auto auto;
  align-items: end;
  gap: 8px;
  padding: 12px;
  border: 1px solid rgba(151, 238, 221, 0.1);
  border-radius: 10px;
  background: rgba(151, 238, 221, 0.025);
}

.admin-empty-state {
  padding: 36px 18px;
  color: rgba(255, 255, 255, 0.36);
  text-align: center;
  font-size: 11px;
}

@media (max-width: 980px) {
  .admin-grid {
    grid-template-columns: 1fr;
  }

  .admin-create-form {
    grid-template-columns: 1fr 1fr;
  }

  .admin-user-row {
    grid-template-columns: minmax(160px, 1.3fr) minmax(120px, 0.8fr) 100px;
  }

  .admin-row-actions {
    grid-column: 1 / -1;
    justify-content: flex-start;
  }
}

@media (max-width: 680px) {
  .admin-workspace {
    padding: 18px 12px 34px;
  }

  .admin-hero {
    align-items: stretch;
    flex-direction: column;
  }

  .admin-refresh {
    align-self: flex-start;
  }

  .admin-create-form,
  .admin-user-row,
  .admin-reset-panel {
    grid-template-columns: 1fr;
  }

  .admin-status-cell,
  .admin-row-actions,
  .admin-reset-panel {
    grid-column: 1;
  }

  .admin-row-actions {
    flex-wrap: wrap;
  }
}



/* =========================================================
   ADMIN AUDIT VISIBILITY
   ========================================================= */

.audit-workspace {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  padding: 28px clamp(18px, 3vw, 42px) 48px;
  background:
    radial-gradient(circle at 82% 0%, rgba(110, 232, 208, 0.04), transparent 30%),
    radial-gradient(circle at 8% 30%, rgba(255, 255, 255, 0.022), transparent 34%);
}

.audit-hero,
.audit-filter-card,
.audit-table-card {
  max-width: 1180px;
}

.audit-filter-card {
  margin: 0 auto 14px;
  padding: 14px;
}

.audit-filter-grid {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) 160px minmax(190px, 1fr) auto auto;
  align-items: end;
  gap: 9px;
}

.audit-filter-grid label {
  min-width: 0;
  display: grid;
  gap: 6px;
}

.audit-filter-grid label > span {
  color: rgba(255, 255, 255, 0.4);
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
}

.audit-filter-grid input,
.audit-filter-grid select {
  width: 100%;
  min-height: 38px;
  border: 1px solid rgba(255, 255, 255, 0.085);
  border-radius: 9px;
  outline: none;
  background: rgba(0, 0, 0, 0.28);
  color: rgba(255, 255, 255, 0.86);
  padding: 0 11px;
  font-size: 11px;
}

.audit-filter-grid input:focus,
.audit-filter-grid select:focus {
  border-color: rgba(151, 238, 221, 0.3);
  box-shadow: 0 0 0 3px rgba(151, 238, 221, 0.04);
}

.audit-filter-grid option {
  background: #0c0e0f;
  color: #f4f4f4;
}

.audit-table-card {
  margin: 0 auto;
  overflow: hidden;
}

.audit-table-heading {
  margin: 0;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.audit-table-scroll {
  width: 100%;
  overflow-x: auto;
}

.audit-table {
  width: 100%;
  min-width: 900px;
  border-collapse: collapse;
  table-layout: fixed;
}

.audit-table th {
  padding: 10px 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  color: rgba(255, 255, 255, 0.32);
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-align: left;
}

.audit-table td {
  padding: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.045);
  color: rgba(255, 255, 255, 0.56);
  font-size: 10px;
  vertical-align: top;
}

.audit-table tr:last-child td {
  border-bottom: 0;
}

.audit-table tbody tr:hover {
  background: rgba(255, 255, 255, 0.015);
}

.audit-table th:nth-child(1),
.audit-table td:nth-child(1) {
  width: 160px;
}

.audit-table th:nth-child(2),
.audit-table td:nth-child(2) {
  width: 110px;
}

.audit-table th:nth-child(4),
.audit-table td:nth-child(4) {
  width: 165px;
}

.audit-table th:nth-child(5),
.audit-table td:nth-child(5) {
  width: 130px;
}

.audit-table th:nth-child(6),
.audit-table td:nth-child(6) {
  width: 80px;
}

.audit-table strong {
  color: rgba(255, 255, 255, 0.82);
}

.audit-table code {
  color: rgba(168, 239, 225, 0.72);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 9px;
  word-break: break-word;
}

.audit-time {
  color: rgba(255, 255, 255, 0.38) !important;
  white-space: nowrap;
}

.audit-question {
  display: -webkit-box;
  overflow: hidden;
  color: rgba(255, 255, 255, 0.72);
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  line-height: 1.45;
}

.audit-error-detail {
  margin-top: 5px;
  color: rgba(255, 150, 150, 0.62);
  font-size: 9px;
  line-height: 1.4;
}

.audit-status {
  display: inline-flex;
  padding: 5px 7px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 999px;
  font-size: 7px;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.audit-status.success {
  border-color: rgba(123, 231, 211, 0.16);
  background: rgba(123, 231, 211, 0.045);
  color: rgba(167, 239, 225, 0.75);
}

.audit-status.warning {
  border-color: rgba(244, 205, 112, 0.16);
  background: rgba(244, 205, 112, 0.04);
  color: rgba(244, 213, 145, 0.72);
}

.audit-status.error {
  border-color: rgba(255, 120, 120, 0.16);
  background: rgba(255, 90, 90, 0.04);
  color: rgba(255, 160, 160, 0.75);
}

@media (max-width: 860px) {
  .audit-filter-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 560px) {
  .audit-workspace {
    padding: 18px 12px 34px;
  }

  .audit-filter-grid {
    grid-template-columns: 1fr;
  }
}


/* ==========================================================
   BUNDLE V2 — ACTIVE DATASET INTELLIGENCE
   ========================================================== */

.dataset-intelligence {
  width: min(100%, 760px);
  margin: 8px 0 26px;
  padding: 18px;
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 18px;
  background:
    linear-gradient(
      145deg,
      rgba(255, 255, 255, 0.035),
      rgba(255, 255, 255, 0.012)
    );
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.025),
    0 18px 50px rgba(0, 0, 0, 0.18);
  text-align: left;
}

.dataset-intelligence-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.dataset-kicker,
.dataset-detail-title {
  display: block;
  margin-bottom: 6px;
  color: rgba(158, 232, 218, 0.58);
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.16em;
}

.dataset-intelligence h2 {
  margin: 0;
  color: rgba(255, 255, 255, 0.92);
  font-size: 18px;
  font-weight: 650;
  letter-spacing: -0.02em;
  text-transform: capitalize;
}

.dataset-refresh,
.dataset-explain {
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.025);
  color: rgba(255, 255, 255, 0.66);
  cursor: pointer;
}

.dataset-refresh {
  padding: 8px 10px;
  font-size: 10px;
}

.dataset-refresh:hover,
.dataset-explain:hover {
  border-color: rgba(136, 226, 210, 0.22);
  background: rgba(126, 226, 207, 0.045);
  color: rgba(200, 247, 238, 0.88);
}

.dataset-refresh:disabled {
  cursor: default;
  opacity: 0.5;
}

.dataset-profile-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 16px;
}

.dataset-profile-meta > span {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
  padding: 10px 11px;
  border: 1px solid rgba(255, 255, 255, 0.055);
  border-radius: 11px;
  background: rgba(0, 0, 0, 0.12);
  color: rgba(255, 255, 255, 0.32);
  font-size: 8px;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.dataset-profile-meta strong {
  overflow: hidden;
  color: rgba(255, 255, 255, 0.78);
  font-size: 11px;
  font-weight: 600;
  text-overflow: ellipsis;
  text-transform: none;
  white-space: nowrap;
}

.dataset-quick-summary {
  margin-top: 12px;
  padding: 14px 15px;
  border-left: 2px solid rgba(136, 226, 210, 0.34);
  border-radius: 0 12px 12px 0;
  background: rgba(126, 226, 207, 0.025);
}

.dataset-quick-summary > span {
  color: rgba(157, 231, 217, 0.52);
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.dataset-quick-summary p {
  max-width: none;
  margin: 7px 0 0;
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
  line-height: 1.65;
}

.dataset-profile-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 12px;
}

.dataset-explain {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 8px 11px;
  font-size: 10px;
}

.dataset-profile-actions small {
  color: rgba(255, 255, 255, 0.26);
  font-size: 8px;
  letter-spacing: 0.05em;
}

.dataset-deep-analysis {
  display: grid;
  gap: 15px;
  margin-top: 15px;
  padding-top: 15px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}

.dataset-measure-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 7px;
}

.dataset-measure-grid article {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border: 1px solid rgba(255, 255, 255, 0.055);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.11);
}

.dataset-measure-grid article > span {
  overflow: hidden;
  color: rgba(255, 255, 255, 0.35);
  font-size: 8px;
  text-overflow: ellipsis;
  text-transform: capitalize;
  white-space: nowrap;
}

.dataset-measure-grid article > strong {
  color: rgba(255, 255, 255, 0.82);
  font-size: 14px;
  font-weight: 650;
}

.dataset-measure-grid article > small {
  color: rgba(255, 255, 255, 0.28);
  font-size: 8px;
}

.dataset-breakdown-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.dataset-breakdown-card {
  padding: 11px;
  border: 1px solid rgba(255, 255, 255, 0.055);
  border-radius: 11px;
  background: rgba(0, 0, 0, 0.09);
}

.dataset-breakdown-card > div {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.dataset-breakdown-card > div strong {
  color: rgba(255, 255, 255, 0.72);
  font-size: 10px;
  text-transform: capitalize;
}

.dataset-breakdown-card > div span {
  color: rgba(255, 255, 255, 0.25);
  font-size: 8px;
}

.dataset-breakdown-card ol {
  display: grid;
  gap: 5px;
  margin: 9px 0 0;
  padding: 0;
  list-style: none;
}

.dataset-breakdown-card li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  color: rgba(255, 255, 255, 0.46);
  font-size: 9px;
}

.dataset-breakdown-card li strong {
  color: rgba(176, 236, 225, 0.63);
  font-weight: 600;
}

.dataset-profile-state {
  margin-top: 14px;
  padding: 12px;
  border: 1px dashed rgba(255, 255, 255, 0.07);
  border-radius: 10px;
  color: rgba(255, 255, 255, 0.4);
  font-size: 10px;
}

.dataset-profile-error {
  display: flex;
  flex-direction: column;
  gap: 4px;
  border-color: rgba(255, 130, 130, 0.12);
  color: rgba(255, 170, 170, 0.62);
}

.dataset-profile-error strong {
  color: rgba(255, 185, 185, 0.78);
}

@media (max-width: 700px) {
  .dataset-profile-meta,
  .dataset-measure-grid {
    grid-template-columns: 1fr 1fr;
  }

  .dataset-breakdown-grid {
    grid-template-columns: 1fr;
  }

  .dataset-profile-actions {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 470px) {
  .dataset-intelligence {
    padding: 14px;
  }

  .dataset-profile-meta,
  .dataset-measure-grid {
    grid-template-columns: 1fr;
  }

  .dataset-intelligence-head {
    align-items: stretch;
    flex-direction: column;
  }

  .dataset-refresh {
    align-self: flex-start;
  }
}



/* Bundle assistant lightweight Markdown rendering */
.message-text :global(strong),
.deep-analysis-text :global(strong) {
  font-weight: 700;
  color: inherit;
}

.message-text :global(em),
.deep-analysis-text :global(em) {
  font-style: italic;
}

.message-text :global(code),
.deep-analysis-text :global(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 0.92em;
  padding: 0.08em 0.32em;
  border-radius: 5px;
  background: rgba(255, 255, 255, 0.07);
}

/* Bundle v2 Stage 8 — per-answer deep analysis */

.explain-more-button:disabled {
  cursor: progress;
  opacity: 0.55;
}

.deep-analysis-panel {
  margin-top: 11px;
  padding: 13px 14px;
  border: 1px solid rgba(137, 229, 213, 0.12);
  border-left: 2px solid rgba(137, 229, 213, 0.38);
  border-radius: 0 12px 12px 0;
  background:
    linear-gradient(
      135deg,
      rgba(125, 224, 207, 0.035),
      rgba(255, 255, 255, 0.012)
    );
}

.deep-analysis-label {
  margin-bottom: 7px;
  color: rgba(158, 232, 218, 0.56);
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.14em;
}

.deep-analysis-panel p {
  margin: 0;
  color: rgba(255, 255, 255, 0.72);
  font-size: 12px;
  line-height: 1.68;
}

.deep-analysis-footnote {
  margin-top: 9px;
  color: rgba(255, 255, 255, 0.28);
  font-size: 8px;
  letter-spacing: 0.04em;
}

.deep-analysis-error {
  margin-top: 9px;
  padding: 8px 10px;
  border: 1px solid rgba(255, 130, 130, 0.12);
  border-radius: 9px;
  background: rgba(255, 95, 95, 0.035);
  color: rgba(255, 178, 178, 0.72);
  font-size: 9px;
}


/* Bundle v2 Stage 10.2 — RAG evidence citations */

.rag-citations {
  display: grid;
  gap: 7px;
  margin-top: 10px;
  padding: 10px 11px;
  border: 1px solid rgba(255, 255, 255, 0.07);
  border-radius: 10px;
  background: rgba(0, 0, 0, 0.09);
}

.rag-citations-title {
  margin-bottom: 2px;
  color: rgba(158, 232, 218, 0.52);
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.13em;
}

.rag-citation-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.rag-citation-index {
  flex: 0 0 auto;
  color: rgba(158, 232, 218, 0.68);
  font-size: 9px;
  font-weight: 700;
}

.rag-citation-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 2px;
}

.rag-citation-copy strong {
  overflow: hidden;
  color: rgba(255, 255, 255, 0.7);
  font-size: 9px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rag-citation-copy small {
  color: rgba(255, 255, 255, 0.3);
  font-size: 8px;
}

</style>
