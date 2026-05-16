import { Component, Input, OnChanges, ViewChild, ElementRef, AfterViewChecked } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatchService } from '../../services/match';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

@Component({
  selector: 'app-chat',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './chat.html',
  styleUrl: './chat.scss',
})
export class ChatComponent implements OnChanges, AfterViewChecked {
  @Input() analysis = '';
  @Input() language = 'English';
  @ViewChild('messagesEnd') messagesEnd!: ElementRef;

  messages: Message[] = [];
  input = '';
  loading = false;
  isOpen = true;

  readonly suggestions = [
    'What was my biggest positioning mistake?',
    'How can I improve my CS?',
    'When should I have recalled?',
    'What should I have done differently at objectives?',
  ];

  constructor(private matchService: MatchService) {}

  ngOnChanges(): void {
    // Reset chat when analysis changes
    this.messages = [];
  }

  ngAfterViewChecked(): void {
    this.scrollToBottom();
  }

  scrollToBottom(): void {
    try {
      this.messagesEnd?.nativeElement.scrollIntoView({ behavior: 'smooth' });
    } catch {}
  }

  send(text?: string): void {
    const question = (text ?? this.input).trim();
    if (!question || this.loading) return;

    this.messages.push({ role: 'user', content: question });
    this.input = '';
    this.loading = true;

    const history = this.messages.slice(0, -1).map(m => ({ role: m.role, content: m.content }));

    this.matchService.chat(this.analysis, history, question, this.language).subscribe({
      next: (res) => {
        this.messages.push({ role: 'assistant', content: res.reply });
        this.loading = false;
      },
      error: () => {
        this.messages.push({ role: 'assistant', content: 'Something went wrong. Please try again.' });
        this.loading = false;
      },
    });
  }

  onKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.send();
    }
  }
}
