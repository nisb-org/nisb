const CODE_LANG_MAP = {
  py: 'python',
  js: 'javascript',
  ts: 'typescript',
  jsx: 'jsx',
  tsx: 'tsx',
  java: 'java',
  c: 'c',
  cpp: 'cpp',
  h: 'c',
  hpp: 'cpp',
  go: 'go',
  rs: 'rust',
  php: 'php',
  rb: 'ruby',
  swift: 'swift',
  kt: 'kotlin',
  scala: 'scala',
  sh: 'bash',
  bash: 'bash',
  zsh: 'bash',
  sql: 'sql',
  yaml: 'yaml',
  yml: 'yaml',
  json: 'json',
  xml: 'xml',
  html: 'html',
  css: 'css',
  scss: 'scss',
  sass: 'sass',
  less: 'less'
}

export function isCodeFile(filename) {
  return /\.(py|js|ts|jsx|tsx|java|c|cpp|h|hpp|go|rs|php|rb|swift|kt|scala|sh|bash|zsh|sql|yaml|yml|json|xml|html|css|scss|sass|less)$/i.test(
    String(filename || '')
  )
}

export function getCodeLanguage(filename) {
  const parts = String(filename || '').split('.')
  const ext = String(parts.pop() || '').toLowerCase()
  return CODE_LANG_MAP[ext] || 'text'
}

export function isPdfFile(name) {
  return /\.pdf$/i.test(String(name || ''))
}
