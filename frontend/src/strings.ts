/**
 * Every piece of text the app shows, in one place.
 *
 * Written in simple Banglish for now. To add a Bangla-script or English version later,
 * create another object of type `Strings` (TypeScript will list anything missing) and
 * pick one based on a setting instead of exporting `banglish` directly.
 */

const banglish = {
  appTitle: 'Baki Khata',

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

  // Edit / manual entry
  editTitle: 'Thik kore din',
  manualTitle: 'Nije likhun',
  amountInvalid: 'Shothik taka likhun (1 theke 1 koti)',
  nameRequired: 'Customer-er naam likhun',

  // After saving
  savedTitle: 'Save hoyeche!',
  savedNewCustomer: (name: string) => `Notun customer ${name} jog hoyeche.`,
  newBalanceOf: (name: string) => `${name}-er notun hisab`,
  close: 'Thik ache',

  // Recent transactions
  recentTitle: 'Shesh 10 ta hisab',
  recentEmpty: 'Ekhono kono hisab nei. Upore prothom hisab likhun.',
  loading: 'Load hocche...',
  recentFailed: 'Hisab load hoyni.',
  retry: 'Abar chesta korun',
  today: 'Aj',
  yesterday: 'Gotokal',
  daysAgo: (days: number) => `${days} din age`,

  // Errors. Each one ends by telling the shopkeeper what to do next.
  errors: {
    network: 'Internet ba server-e somossa. Abar chesta korun, ba niche nije likhun.',
    aiFailed: 'AI ei line-ta bujhte pareni. Niche nije likhe din.',
    aiUnavailable: 'AI ekhon kaj korche na. Niche nije likhe din.',
    notTransaction: 'Naam ba taka khuje paini. Niche nije likhe din.',
    lowConfidence: 'AI puro nishchit na. Ekbar dekhe thik kore din.',
    shopNotFound: 'Dokan pawa jayni. Backend-e demo dokan banan (README dekhun).',
    duplicateCustomer: 'Ei naame customer age thekei ache. Upore theke bachun, ba alada note din.',
    invalidData: 'Kichu tottho thik nei. Dekhe abar save korun.',
    saveFailed: 'Save hoyni. Abar chesta korun.',
    unknown: 'Kichu ekta somossa hoyeche. Abar chesta korun.',
    // Voice input
    micPermission: 'Mic chalu korar onumoti nei. Browser-er setting-e ei site-ke mic-er onumoti din, ba likhe din.',
    micInsecure: 'Ei address-e browser mic chalu korte dey na (https lagbe). Ekhon likhe din.',
    micNoSpeech: 'Kichu shunte paini. Mic-er kache eshe ektu jore abar bolun.',
    micNotFound: 'Kono mic pawa jayni. Mic lagiye abar chesta korun, ba likhe din.',
    micNetwork: 'Internet-e somossa, tai voice kaj korche na. Abar chesta korun, ba likhe din.',
    micLanguage: 'Ei browser ei bhasha bujhe na. Voice setting-e onno bhasha bachun.',
    micServerOff: 'Server-e voice chalu nei. Browser diye bolun, ba likhe din.',
    micTooLong: 'Onek lomba hoye geche. Chhoto kore ek line-e abar bolun.',
    micFailed: 'Voice bujhte pareni. Abar bolun, ba likhe din.',
  },
}

export type Strings = typeof banglish

export const strings: Strings = banglish
