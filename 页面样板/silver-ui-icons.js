(()=>{
const paths={
'⌂':'<path d="m3 10 9-7 9 7v11h-7v-7h-4v7H3z"/>',
'↗':'<circle cx="6" cy="5" r="2"/><circle cx="18" cy="19" r="2"/><path d="M8 5h7a4 4 0 0 1 0 8H9a3 3 0 0 0 0 6h7"/>',
'♬':'<path d="M4 14v-3a8 8 0 0 1 16 0v3M4 13H2v7h5v-7zm16 0h2v7h-5v-7z"/>',
'♡':'<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8z"/>',
'▧':'<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 5-5 4 4 4-6 5 7"/>',
'♧':'<path d="m12 3 8 4v10l-8 4-8-4V7zM12 3v18M4 7l8 4 8-4"/>',
'◉':'<circle cx="12" cy="7" r="3.5"/><path d="M5 21a7 7 0 0 1 14 0"/>'};
function icons(){document.querySelectorAll('.bottom button span,.tile .icon').forEach(el=>{const p=paths[el.textContent.trim()];if(p)el.innerHTML=`<svg class="ui-icon" viewBox="0 0 24 24" aria-hidden="true">${p}</svg>`})}
new MutationObserver(icons).observe(document.getElementById('surface'),{childList:true});icons();
})();
