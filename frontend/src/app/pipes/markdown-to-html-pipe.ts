import { Pipe, PipeTransform } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

@Pipe({ name: 'markdownToHtml', standalone: true })
export class MarkdownToHtmlPipe implements PipeTransform {
  constructor(private sanitizer: DomSanitizer) {}

  transform(value: string): SafeHtml {
    if (!value) return '';

    const lines = value.split('\n');
    const output: string[] = [];
    let inList = false;

    for (const raw of lines) {
      let line = raw
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>');

      // Highlight numbers with units (e.g. 8.5 CS/min, 34min, 15k gold)
      line = line.replace(/(\d+\.?\d*\s*(CS\/min|cs\/min|CS|gold|g|dmg|min|%|k|K|vision|ward))/g,
        '<span class="hl-stat">$1</span>');

      // Highlight standalone numbers that look significant (e.g. 6/6/4, 288)
      line = line.replace(/\b(\d+\/\d+\/\d+)\b/g, '<span class="hl-kda">$1</span>');

      // Highlight time references (e.g. 14min, at 8min, 5-minute)
      line = line.replace(/\b(\d+)\s*-?\s*min(ute)?s?\b/gi, '<span class="hl-time">$&</span>');

      // Highlight Challenger/good keywords
      line = line.replace(/\b(Challenger[- ]standard|excellent|strong|efficient|correct|well-timed|dominant)\b/gi,
        '<span class="hl-good">$&</span>');

      // Highlight bad keywords
      line = line.replace(/\b(mistake|error|wrong|missed|failed|poor|weak|unacceptable|violation|overextend|overextended|behind|deficit)\b/gi,
        '<span class="hl-bad">$&</span>');

      if (/^### (.+)$/.test(line)) {
        if (inList) { output.push('</ul>'); inList = false; }
        output.push(`<h3>${line.replace(/^### /, '')}</h3>`);
      } else if (/^## (.+)$/.test(line)) {
        if (inList) { output.push('</ul>'); inList = false; }
        output.push(`<h2>${line.replace(/^## /, '')}</h2>`);
      } else if (/^---$/.test(raw)) {
        if (inList) { output.push('</ul>'); inList = false; }
        output.push('<hr>');
      } else if (/^- (.+)$/.test(line)) {
        if (!inList) { output.push('<ul>'); inList = true; }
        output.push(`<li>${line.replace(/^- /, '')}</li>`);
      } else if (/^[✅❌🎯⚠️🔧]/.test(raw)) {
        if (inList) { output.push('</ul>'); inList = false; }
        output.push(`<p class="section-header">${line}</p>`);
      } else if (line.trim() === '') {
        if (inList) { output.push('</ul>'); inList = false; }
        output.push('<br>');
      } else {
        if (inList) { output.push('</ul>'); inList = false; }
        output.push(`<p>${line}</p>`);
      }
    }

    if (inList) output.push('</ul>');

    // Strip any script tags or event handlers before trusting
    const safe = output.join('')
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/on\w+="[^"]*"/gi, '')
      .replace(/on\w+='[^']*'/gi, '');
    return this.sanitizer.bypassSecurityTrustHtml(safe);
  }
}
