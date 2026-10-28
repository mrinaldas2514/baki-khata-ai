/**
 * Every piece of text the app shows, in one place.
 *
 * Written in simple Banglish for now. To add a Bangla-script or English version later,
 * create another object of type `Strings` (TypeScript will list anything missing) and
 * pick one based on a setting instead of exporting `banglish` directly.
 */

const banglish = {
  appTitle: 'Baki Khata',

  // Login and register
  auth: {
    loginTitle: 'Login korun',
    loginSubtitle: 'Apnar dokan-er khata khulun',
    loginLabel: 'Mobile number ba email',
    loginPlaceholder: 'Jemon: 01711-000001',
    password: 'Password',
    showPassword: 'Password dekhun',
    show: 'Dekhun',
    hide: 'Lukan',
    loginButton: 'Login korun',
    loggingIn: 'Login hocche...',
    noAccount: 'Account nei?',
    toRegister: 'Notun account khulun',
    haveAccount: 'Age thekei account ache?',
    toLogin: 'Login korun',
    registerTitle: 'Notun account khulun',
    registerSubtitle: 'Ekbar likhe nin. Tarpor shudhu mobile number ar password diye login.',
    yourName: 'Apnar naam',
    shopName: 'Dokan-er naam',
    phone: 'Mobile number',
    phonePlaceholder: '01711-000001 ba +91 98765 43210',
    phoneHint: 'Ei number diye login korben.',
    email: 'Email (na thakle khali rakhun)',
    newPassword: 'Password (kom-pokkhe 8 ta okkhor)',
    registerButton: 'Account khulun',
    registering: 'Account khola hocche...',
    wrongLogin: 'Mobile number/email ba password thik nei. Dekhe abar likhun.',
    loginRequired: 'Mobile number ba email likhun',
    passwordRequired: 'Password likhun',
    sessionExpired: 'Login-er shomoy shesh hoye geche. Abar login korun.',
    loggedOut: 'Logout hoyeche. Abar dekha hobe!',
    accountDeleted: 'Account ar sob hisab muche fela hoyeche.',
    accountExists: 'Ei number ba email diye age thekei account ache. Login korun.',
    nameRequired: 'Apnar naam likhun',
    shopRequired: 'Dokan-er naam likhun',
    phoneRequired: 'Mobile number likhun',
    passwordShort: 'Password kom-pokkhe 8 ta okkhor-er hote hobe',
    emailInvalid: 'Email thik nei (jemon: karim@gmail.com)',
    consentRequired: 'Age niche pore tick din',
  },

  // The privacy note on registration (version: CONSENT_VERSION in config.ts)
  consent: {
    title: 'Apnar hisab, apnar odhikar',
    points: [
      'Apni je line likhen ba bolen, sheta bujhte AI service-e (Groq) pathano hoy.',
      'Browser nije voice bujhte na parle, apnar voice lekhar jonno server-e (Groq) pathano hoy.',
      'Apnar tottho kauke bikri kora hoy na, ar loan ba credit-er jonno beboher kora hoy na.',
      'Settings theke jekono shomoy AI bondho korte, sob hisab download korte ba account muche dite paren.',
    ],
    agree: 'Ami pore bujhechi ar raji achi',
  },

  // Settings
  settings: {
    open: 'Settings',
    title: 'Settings',
    account: 'Apnar account',
    aiTitle: 'AI bondho rakhun',
    aiOnHint: 'Ekhon AI chalu: apnar line AI service-e jay, beshi thik bujhe.',
    aiOffHint:
      'AI bondho: kichui AI service-e jay na. Shohoj niyome bujhbe, ar na bujhle nije likhben. Server diye voice-o bondho.',
    aiSaving: 'Bodlano hocche...',
    aiFailed: 'Bodlano jayni. Abar chesta korun.',
    aiOffBanner: 'AI bondho ache: shohoj niyome bujhchi. Bhul hole thik kore din.',
    exportTitle: 'Data export (CSV)',
    exportHint: 'Sob customer ar sob hisab ekta file-e. Excel-e khola jay.',
    exportButton: 'Download korun',
    exporting: 'File toiri hocche...',
    exportFailed: 'Download hoyni. Abar chesta korun.',
    logout: 'Logout',
    loggingOut: 'Logout hocche...',
    deleteTitle: 'Account muchhe din',
    deleteHint:
      'Account, dokan, sob customer ar sob hisab chirodiner jonno muche jabe. Age CSV download kore rakhte paren.',
    deleteButton: 'Account muchhe din',
    deleteConfirmTitle: 'Sob kichu muche felben?',
    deleteConfirmBody:
      'Ei account, dokan-er sob customer ar sob hisab muche jabe. Ar fire pawa jabe na. Nishchit hole password likhun.',
    deleteConfirmYes: 'Hya, sob muche din',
    deleteConfirmNo: 'Na, rakhun',
    deleting: 'Muchchi...',
    wrongPassword: 'Password thik nei.',
    deleteFailed: 'Muchte pareni. Abar chesta korun.',
  },

  // Add / edit a customer
  customerForm: {
    addTitle: 'Notun customer',
    editTitle: 'Customer-er tottho',
    addButton: '+ Notun customer',
    editButton: 'Tottho bodlan',
    name: 'Naam',
    phone: 'Mobile number (na thakle khali rakhun)',
    phonePlaceholder: '01711-000001',
    note: 'Elaka / note (jemon: Bazar road)',
    phoneInvalid: 'Bangladesh (01XXXXXXXXX ba +880) ba India (+91) mobile number likhun',
    saved: 'Customer-er tottho save hoyeche',
    created: (name: string) => `${name} jog hoyeche`,
  },

  // Smart entry
  entryLabel: 'Ki hisab likhben?',
  entryPlaceholder: 'Jemon: rahim bhai 2 kg chal 120 taka baki',
  submit: 'Hisab korun',
  parsing: 'Bujhchi... ektu opekkha korun',

  // Voice input (mic button next to the box)
  voice: {
    micIdle: 'Bole likhun',
    micListening: 'Shunchi... bola hole chhere din',
    micProcessing: 'Lekha hocche...',
    micRetry: 'Abar bolun',
    buttonIdle: 'Bolun',
    buttonListening: 'Shunchi',
    buttonProcessing: 'Lekha...',
    holdHint: 'Mic chepe dhore bolun, bola hole chhere din. Ba ekbar chapun, shesh hole abar chapun.',
    listeningHint: 'Shunchi... bola shesh hole chhere din (ba abar chapun).',
    processingHint: 'Apnar kotha lekha hocche...',
    checkTranscript: 'Dekhe nin. Kono bhul thakle thik kore "Hisab korun" chapun.',
    settingsTitle: (language: string) => `Voice: ${language}`,
    languageLabel: 'Kon bhashay bolben?',
    languages: {
      'bn-BD': 'Bangla (Bangladesh)',
      'bn-IN': 'Bangla (India)',
      'en-IN': 'English / Banglish (India)',
    },
    autoSubmit: 'Bola shesh holei nije theke "Hisab korun"',
    preferServer: 'Server diye shunun (beshi thik bujhe, ektu deri hoy)',
    serverOnly: 'Ei browser-e voice server diye shona hoy.',
  },

  // Confirmation card
  confirmTitle: 'Thik ache to?',
  // The small label on a confirmation card: who read the sentence.
  parser: {
    readBy: 'Ke porlo:',
    llm: 'AI',
    rules: 'AI chhara',
    llmTitle: (model: string) => `AI diye pora (${model})`,
    rulesTitle: 'AI chhara, shohoj niyom diye pora',
  },
  youWrote: 'Apni likhechen',
  save: 'Save korun',
  saving: 'Save hocche...',
  edit: 'Thik kore din',
  cancel: 'Bad din',
  checkThis: 'Ekbar mile nin',
  fuzzyMatch: (said: string, name: string) => `"${said}" mane ki ${name}? Dekhe nin.`,
  whichCustomer: 'Kon customer? Ekjon bachun',
  orExisting: 'Naki ager kono customer?',
  pickCustomerFirst: 'Age customer bachun',

  // Customer
  customer: 'Customer',
  customerNamePlaceholder: 'Customer-er naam',
  newCustomer: 'Notun customer',
  newCustomerNamed: (name: string) => `Notun customer: ${name}`,
  newCustomerHint: 'Save korle khatay notun naam jog hobe',
  existingCustomer: 'Ager customer',
  sameNameExists: 'Ei naame customer ache. Upore theke bachun, na hole alada note din.',
  note: 'Elaka / note (jemon: Bazar road)',

  // Balance (positive = owes the shop, negative = paid in advance)
  currentBalance: 'Ekhon',
  balanceOwes: (amount: string) => `Baki ${amount}`,
  balanceAdvance: (amount: string) => `Agrim ${amount}`,
  balanceClear: 'Hisab clear',

  // Transaction fields
  amount: 'Koto taka?',
  type: 'Ki holo?',
  typeCredit: 'Baki',
  typePayment: 'Joma',
  typeCreditHint: 'Customer baki nilo',
  typePaymentHint: 'Customer taka dilo',
  item: 'Jinis (na thakle khali rakhun)',
  itemShort: 'Jinis',
  date: 'Kobe?',
  dateInvalid: 'Shothik tarikh din (agamir tarikh hobe na)',

  // Edit / manual entry
  editTitle: 'Thik kore din',
  manualTitle: 'Nije likhun',
  amountInvalid: 'Shothik taka likhun (1 theke 1 koti)',
  nameRequired: 'Customer-er naam likhun',

  // Several customers in one sentence
  multi: {
    title: (count: number) => `${count} ta hisab bujhechi`,
    hint: 'Protita dekhe nin. Bhul thakle "Thik kore din", dorkar na hole "Bad din".',
    entryLabel: (n: number, name: string) => `Hisab ${n}: ${name}`,
    editTitle: (n: number) => `Hisab ${n} thik kore din`,
    remove: 'Bad din',
    saveAll: (count: number) => `Sob save korun (${count} ta)`,
    pickAll: 'Age protita hisab-er customer bachun',
    savedTitle: (count: number) => `${count} ta hisab save hoyeche!`,
  },

  // Undo right after saving
  undo: {
    button: (seconds: number) => `Bhul hoyeche? Undo (${seconds})`,
    label: 'Bhul hoyeche? Undo',
    undoing: 'Undo hocche...',
    done: 'Undo hoyeche. Line-ta abar box-e ache: thik kore abar "Hisab korun" chapun.',
    failed: 'Undo hoyni. Customer-er khata theke hisab-ta muche din.',
  },

  // After saving
  savedTitle: 'Save hoyeche!',
  savedNewCustomer: (name: string) => `Notun customer ${name} jog hoyeche.`,
  newBalanceOf: (name: string) => `${name}-er notun hisab`,
  close: 'Thik ache',
  closeDialog: 'Bondho korun',

  // Recent transactions
  recentTitle: 'Shesh 10 ta hisab',
  recentEmpty: 'Ekhono kono hisab nei. Upore prothom hisab likhun.',
  loading: 'Load hocche...',
  recentFailed: 'Hisab load hoyni.',
  retry: 'Abar chesta korun',
  today: 'Aj',
  yesterday: 'Gotokal',
  daysAgo: (days: number) => `${days} din age`,

  // Bottom navigation
  nav: {
    label: 'Prodhan menu',
    hisab: 'Hisab',
    customers: 'Customer',
    dashboard: 'Dashboard',
  },

  // Customer list
  customersTitle: 'Customer',
  searchLabel: 'Customer khujun',
  searchPlaceholder: 'Naam, elaka ba phone',
  clearSearch: 'Khoja muchun',
  sortLabel: 'Sajano',
  sort: {
    'most-owed': 'Beshi baki',
    'oldest-owed': 'Purono baki',
    name: 'Naam',
  },
  customerCount: (count: number) => `${count} jon customer`,
  customersWithBaki: (count: number, total: string) => `${count} jon-er kache mot ${total} baki`,
  customersEmpty: 'Ekhono kono customer nei. "Hisab" theke prothom hisab likhun.',
  noSearchResult: (query: string) => `"${query}" naame kauke paini.`,
  customersFailed: 'Customer-er list load hoyni.',
  owedForDays: (days: number) => (days === 0 ? 'Aj theke baki' : `${days} din dhore baki`),
  balanceClearShort: 'Clear',

  // Customer khata
  backToCustomers: 'Sob customer',
  khataFailed: 'Khata load hoyni.',
  customerNotFound: 'Ei customer-ke pawa jayni.',
  call: (phone: string) => `Phone: ${phone}`,
  noPhone: 'Phone number nei',
  addCredit: 'Baki likhun',
  addPayment: 'Joma likhun',
  sendReminder: 'Reminder pathan',
  historyTitle: 'Hisab-er khata',
  historyCount: (shown: number, total: number) => `${total} ta hisab-er moddhe ${shown} ta dekhacche`,
  historyHint: 'Kono hisab thik korte ba muchte tar upor chapun.',
  historyEmpty: 'Ei customer-er ekhono kono hisab nei. Upore "Baki likhun" ba "Joma likhun" chapun.',
  showMore: 'Aro dekhun',
  loadingMore: 'Aro load hocche...',
  showMoreFailed: 'Aro load hoyni. Abar chapun.',
  balanceAfter: 'Tarpor',

  // Quick entry / edit on the khata screen
  quickEntryTitle: (type: string, name: string) => `${name}: ${type} likhun`,
  editTransactionTitle: 'Hisab thik korun',
  deleteTransaction: 'Muche felun',
  deleteConfirmTitle: 'Ei hisab muche felben?',
  deleteConfirmBody: (amount: string, type: string, when: string) =>
    `${when}-er ${amount} ${type} muche jabe. Ar fire pawa jabe na.`,
  deleteConfirmYes: 'Hya, muche felun',
  deleteConfirmNo: 'Na, rakhun',
  deleting: 'Muchchi...',
  savedEntry: 'Save hoyeche',
  deletedEntry: 'Muche fela hoyeche',
  deleteFailed: 'Muchte pareni. Abar chesta korun.',

  // Reminder
  reminderTitle: (name: string) => `${name}-ke reminder`,
  reminderLoading: 'Message toiri hocche...',
  reminderFailed: 'Message toiri hoyni. Abar chesta korun.',
  reminderLabel: 'Message (dorkar hole bodlate paren)',
  reminderHint: 'WhatsApp khulbe, message lekha thakbe. Apni dekhe "Send" chapben.',
  reminderNoPhone:
    'Ei customer-er phone number nei. Number dile WhatsApp-e pathano jabe, na hole message copy kore nije pathan.',
  reminderAddPhone: 'Phone number save korun',
  reminderPhoneSaved: 'Phone number save hoyeche',
  openWhatsApp: 'WhatsApp-e khulun',
  copyMessage: 'Message copy korun',
  copied: 'Copy hoyeche!',
  copyFailed: 'Copy hoyni. Message chepe dhore nije copy korun.',

  // Dashboard
  dashboardTitle: 'Dashboard',
  totalBaki: 'Mot baki',
  totalBakiFrom: (count: number) => `${count} jon customer-er kache`,
  todayPayment: 'Ajker joma',
  entrySpeed: 'Gore ekta hisab',
  entrySpeedValue: (seconds: string) => `${seconds} second`,
  entrySpeedDetail: (count: number) => `Shesh ${count} ta hisab-er median (likha shuru theke save porjonto)`,
  entrySpeedNone: 'Hisab likhle ekhane dekhabe, ekta hisab likhte koto shomoy lage.',
  todayNewCredit: 'Ajker notun baki',
  weekTitle: 'Shesh 7 din',
  weekLegendCredit: 'Notun baki',
  weekLegendPayment: 'Joma',
  weekDayDetail: (day: string, credit: string, payment: string) => `${day}: notun baki ${credit}, joma ${payment}`,
  weekTableCaption: 'Shesh 7 diner notun baki ar joma',
  weekDay: 'Din',
  weekEmpty: 'Shesh 7 dine kono hisab nei.',
  weekMax: (amount: string) => `shorbochcho ${amount}`,
  topTitle: 'Shobcheye beshi baki',
  topEmpty: 'Karo kache baki nei.',
  overdueTitle: (days: number) => `${days} diner beshi purono baki`,
  overdueEmpty: (days: number) => `${days} diner beshi purono baki karo nei.`,
  overdueSince: (days: number) => `${days} din dhore`,
  dashboardFailed: 'Dashboard load hoyni.',

  // Errors. Each one ends by telling the shopkeeper what to do next.
  errors: {
    network: 'Internet ba server-e somossa. Abar chesta korun, ba niche nije likhun.',
    aiFailed: 'AI ei line-ta bujhte pareni. Niche nije likhe din.',
    aiUnavailable: 'AI ekhon kaj korche na. Niche nije likhe din.',
    notTransaction: 'Naam ba taka khuje paini. Niche nije likhe din.',
    lowConfidence: 'AI puro nishchit na. Ekbar dekhe thik kore din.',
    shopNotFound: 'Dokan pawa jayni. Logout kore abar login korun.',
    duplicateCustomer: 'Ei naame customer age thekei ache. Upore theke bachun, ba alada note din.',
    invalidData: 'Kichu tottho thik nei. Dekhe abar save korun.',
    saveFailed: 'Save hoyni. Abar chesta korun.',
    unknown: 'Kichu ekta somossa hoyeche. Abar chesta korun.',
    rateLimited: (seconds: number) =>
      `Onek bar chesta hoyeche. ${seconds < 90 ? `${seconds} second` : `${Math.ceil(seconds / 60)} minute`} por abar chesta korun.`,
    // Voice input
    micPermission: 'Mic chalu korar onumoti nei. Browser-er setting-e ei site-ke mic-er onumoti din, ba likhe din.',
    micInsecure: 'Ei address-e browser mic chalu korte dey na (https lagbe). Ekhon likhe din.',
    micNoSpeech: 'Kichu shunte paini. Mic-er kache eshe ektu jore abar bolun.',
    micNotFound: 'Kono mic pawa jayni. Mic lagiye abar chesta korun, ba likhe din.',
    micNetwork: 'Internet-e somossa, tai voice kaj korche na. Abar chesta korun, ba likhe din.',
    micLanguage: 'Ei browser ei bhasha bujhe na. Voice setting-e onno bhasha bachun.',
    micServerOff: 'Server-e voice chalu nei. Browser diye bolun, ba likhe din.',
    micTooLong: 'Onek lomba hoye geche. Chhoto kore ek line-e abar bolun.',
    micTooMany: 'Onek bar bola hoyeche. Ek minute por abar bolun, ba ekhon likhe din.',
    micFailed: 'Voice bujhte pareni. Abar bolun, ba likhe din.',
  },
}

export type Strings = typeof banglish

export const strings: Strings = banglish
