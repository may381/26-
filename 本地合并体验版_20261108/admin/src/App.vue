<template>
  <header><strong>银龄智游</strong><span>内容管理</span></header>
  <main><RouterView /></main>
</template>
<style>
body {
  margin: 0;
  color: #17372a;
  background: #f4f8f5;
  font:
    16px/1.6 system-ui,
    sans-serif;
}
header {
  display: flex;
  gap: 24px;
  padding: 24px 5%;
  background: #17372a;
  color: white;
}
main {
  max-width: 1080px;
  margin: 40px auto;
  padding: 0 24px;
}
button {
  padding: 12px 20px;
  border: 0;
  border-radius: 8px;
  background: #24664c;
  color: white;
  font: inherit;
  cursor: pointer;
}
button:disabled {
  opacity: 0.6;
  cursor: wait;
}
input,
textarea {
  box-sizing: border-box;
  width: 100%;
  padding: 12px;
  margin-top: 8px;
  font: inherit;
  border: 1px solid #9cafa4;
  border-radius: 8px;
}
label {
  display: block;
  margin-bottom: 20px;
}
article,
form {
  padding: 24px;
  background: white;
  border-radius: 12px;
  margin: 20px 0;
}
p {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.error {
  color: #a02222;
}
</style>
