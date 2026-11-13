'use strict';
window.addEventListener('load',()=>{
 const tool=new URLSearchParams(location.search).get('tool');
 if(tool==='exchange')document.querySelector('.exchange-entry')?.click();
 if(tool==='import')importDialog.showModal();
 if(tool==='plan')wizardStart();
});
