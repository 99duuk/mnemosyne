const status = document.querySelector('#status');
async function refresh() {
  const result = await chrome.runtime.sendMessage({type: 'STATUS'});
  status.textContent = JSON.stringify(result, null, 2);
}
document.querySelector('#start').onclick = async () => {
  const [tab] = await chrome.tabs.query({active: true, currentWindow: true});
  const result = await chrome.runtime.sendMessage({type: 'ARM', tabId: tab.id,
    blog: document.querySelector('#blog').value.trim(),
    limit: Number(document.querySelector('#limit').value)});
  status.textContent = JSON.stringify(result, null, 2);
};
document.querySelector('#stop').onclick = async () => {
  await chrome.runtime.sendMessage({type: 'STOP'}); await refresh();
};
document.querySelector('#export').onclick = async () => {
  const all = await chrome.storage.local.get(null);
  const records = Object.entries(all).filter(([key]) => key.startsWith('record:')).map(([, value]) => value);
  const url = URL.createObjectURL(new Blob([records.map(x => JSON.stringify(x)).join('\n') + '\n'], {type: 'application/x-ndjson'}));
  const link = document.createElement('a'); link.href = url; link.download = 'mnemosyne-capture.jsonl'; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 30_000);
};
refresh();
