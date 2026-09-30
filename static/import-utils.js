/* File intake utilities, shared by the browser and local validation scripts. */
(function(root, factory) {
  const utils=factory();
  if(typeof module==='object'&&module.exports)module.exports=utils;
  else root.CapitalForgeImport=Object.freeze(utils);
})(typeof globalThis!=='undefined'?globalThis:this,function() {
  'use strict';
  const MAX_FILE_BYTES=100*1024*1024;
  const MAX_ROWS=100000;
  function parseCSV(input) {
    const text=String(input).replace(/^\uFEFF/,'');
    const table=[];let row=[],field='',quoted=false,closed=false;
    function pushField(){row.push(field);field='';closed=false;}
    function pushRow(){pushField();if(row.some(value=>value!==''))table.push(row);row=[];}
    for(let index=0;index<text.length;index++) {
      const char=text[index];
      if(quoted) {
        if(char==='"') {if(text[index+1]==='"'){field+='"';index++;}else{quoted=false;closed=true;}}
        else field+=char;
      } else if(char===',')pushField();
      else if(char==='\r'||char==='\n'){pushRow();if(char==='\r'&&text[index+1]==='\n')index++;}
      else if(closed){if(!/\s/.test(char))throw new Error(`Unexpected text after a closing quote in CSV record ${table.length+1}.`);}
      else if(char==='"'){if(field!=='')throw new Error(`Unexpected quote in CSV record ${table.length+1}.`);quoted=true;}
      else field+=char;
    }
    if(quoted)throw new Error('The CSV ends inside a quoted field. Check the closing quotes.');
    if(field!==''||row.length||closed)pushRow();
    if(!table.length)throw new Error('The CSV is empty. Include a header row and source records.');
    const headers=table.shift().map(value=>value.trim().toLowerCase().replace(/\s+/g,'_'));
    if(headers.some(value=>!value))throw new Error('Every CSV column needs a header.');
    if(new Set(headers).size!==headers.length)throw new Error('CSV headers must be unique.');
    return table.map((values,index)=>{
      if(values.length>headers.length)throw new Error(`CSV record ${index+2} has more values than the header. Quote values containing commas.`);
      const record=Object.create(null);headers.forEach((header,column)=>record[header]=values[column]??'');return record;
    });
  }
  function parseRecords(input,filename) {
    const text=String(input).replace(/^\uFEFF/,'');let rows;
    const lower=String(filename).toLowerCase();
    if(lower.endsWith('.jsonl')||lower.endsWith('.ndjson')) {
      rows=text.split(/\r?\n/).flatMap((line,index)=>{
        if(!line.trim())return [];
        try{return [JSON.parse(line)];}catch(error){throw new Error(`JSONL line ${index+1} is invalid: ${error.message}`);}
      });
    } else if(lower.endsWith('.json')) {
      const parsed=JSON.parse(text);rows=Array.isArray(parsed)?parsed:parsed?.items||parsed?.rows;
      if(!Array.isArray(rows))throw new Error('JSON must contain an array, or an object with an items or rows array.');
    } else rows=parseCSV(text);
    if(!rows.length)throw new Error('This file contains no records.');
    if(rows.length>MAX_ROWS)throw new Error(`A file can contain at most ${MAX_ROWS.toLocaleString()} records. Split larger files.`);
    rows.forEach((row,index)=>{if(!row||typeof row!=='object'||Array.isArray(row))throw new Error(`Record ${index+1} must be an object with named fields.`);});
    return rows;
  }
  function batchRows(rows,maxRows=250,maxBytes=8*1024*1024) {
    const batches=[];const encoder=new TextEncoder();let batch=[],bytes=12,start=0;
    rows.forEach((row,index)=>{
      const size=encoder.encode(JSON.stringify(row)).byteLength+1;
      if(size+12>maxBytes)throw new Error(`Record ${index+1} is too large to import. Reduce its embedded evidence.`);
      if(batch.length&&(batch.length>=maxRows||bytes+size>maxBytes)){batches.push({rows:batch,start});batch=[];bytes=12;start=index;}
      batch.push(row);bytes+=size;
    });
    if(batch.length)batches.push({rows:batch,start});
    return batches;
  }
  return {MAX_FILE_BYTES,MAX_ROWS,parseCSV,parseRecords,batchRows};
});
