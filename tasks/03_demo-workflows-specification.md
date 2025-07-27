# Demo Workflows Specification

## Overview

Three distinct workflows demonstrate different aspects of the container manager: web content processing, AI integration, and document analysis. Each workflow follows consistent patterns while showcasing unique capabilities.

## Data Models

### Core Workflow Models

```python
# demo_workflows/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from container_manager.models import ContainerJob

class WorkflowExecution(models.Model):
    """Base model for tracking workflow executions"""
    
    WORKFLOW_TYPES = [
        ('crawler', 'Web Page Crawler'),
        ('rewriter', 'Text Rewriter'),
        ('analyzer', 'Document Analyzer'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workflow_type = models.CharField(max_length=20, choices=WORKFLOW_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Container job relationship
    container_job = models.ForeignKey(
        ContainerJob, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        help_text="Associated container job"
    )
    
    # Results and errors
    result_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        
    def __str__(self):
        return f"{self.get_workflow_type_display()} - {self.status} ({self.created_at})"
    
    @property
    def duration(self):
        if self.started_at and self.completed_at:
            return self.completed_at - self.started_at
        return None

class WebPageCrawl(models.Model):
    """Web page crawling workflow data"""
    
    execution = models.OneToOneField(
        WorkflowExecution, 
        on_delete=models.CASCADE,
        related_name='crawl_data'
    )
    
    # Input parameters
    url = models.URLField(max_length=1000)
    follow_links = models.BooleanField(default=False)
    max_depth = models.PositiveIntegerField(default=1)
    
    # Extracted data
    title = models.CharField(max_length=500, blank=True)
    content = models.TextField(blank=True)
    word_count = models.PositiveIntegerField(null=True, blank=True)
    links_found = models.JSONField(default=list, blank=True)
    meta_data = models.JSONField(default=dict, blank=True)
    
    def __str__(self):
        return f"Crawl: {self.url[:50]}..."

class TextRewrite(models.Model):
    """Text rewriting workflow data"""
    
    HISTORICAL_FIGURES = [
        ('shakespeare', 'William Shakespeare'),
        ('churchill', 'Winston Churchill'),
        ('lincoln', 'Abraham Lincoln'),
        ('einstein', 'Albert Einstein'),
        ('twain', 'Mark Twain'),
        ('wilde', 'Oscar Wilde'),
        ('hemingway', 'Ernest Hemingway'),
        ('roosevelt', 'Theodore Roosevelt'),
    ]
    
    execution = models.OneToOneField(
        WorkflowExecution, 
        on_delete=models.CASCADE,
        related_name='rewrite_data'
    )
    
    # Input parameters
    original_text = models.TextField()
    historical_figure = models.CharField(max_length=20, choices=HISTORICAL_FIGURES)
    model_used = models.CharField(max_length=50, blank=True)
    
    # Output
    rewritten_text = models.TextField(blank=True)
    transformation_notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Rewrite as {self.get_historical_figure_display()}"

class DocumentAnalysis(models.Model):
    """Document analysis workflow data"""
    
    execution = models.OneToOneField(
        WorkflowExecution, 
        on_delete=models.CASCADE,
        related_name='analysis_data'
    )
    
    # Input
    document_file = models.FileField(upload_to='documents/')
    document_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()  # bytes
    file_type = models.CharField(max_length=50)
    
    # Analysis results
    text_content = models.TextField(blank=True)
    word_count = models.PositiveIntegerField(null=True, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    
    # AI Analysis
    sentiment_score = models.FloatField(null=True, blank=True)  # -1 to 1
    summary = models.TextField(blank=True)
    key_topics = models.JSONField(default=list, blank=True)
    entities = models.JSONField(default=list, blank=True)
    
    def __str__(self):
        return f"Analysis: {self.document_name}"
```

## Workflow 1: Web Page Crawler

### Purpose
Demonstrate HTTP requests, content parsing, and data extraction in a containerized environment.

### Container Template Specification

```yaml
# Container configuration for web crawler
name: "web-page-crawler"
description: "Python environment for web scraping with requests and BeautifulSoup"
docker_image: "python:3.11-slim"
command: ["python", "manage.py", "crawl_webpage"]
environment_variables_text: |
  DJANGO_SETTINGS_MODULE=demo_project.settings
  PYTHONPATH=/app
working_dir: "/app"
cpu_limit: 0.5
memory_limit_mb: 256
timeout_seconds: 300
```

### Management Command

```python
# demo_workflows/management/commands/crawl_webpage.py
import json
import sys
import requests
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand, CommandError
from demo_workflows.models import WorkflowExecution, WebPageCrawl

class Command(BaseCommand):
    help = 'Crawl a web page and extract content'

    def add_arguments(self, parser):
        parser.add_argument('execution_id', type=str, help='WorkflowExecution ID')
        parser.add_argument('--url', type=str, required=True, help='URL to crawl')
        parser.add_argument('--follow-links', action='store_true', help='Follow internal links')
        parser.add_argument('--max-depth', type=int, default=1, help='Maximum crawl depth')

    def handle(self, *args, **options):
        execution_id = options['execution_id']
        
        try:
            # Get workflow execution
            execution = WorkflowExecution.objects.get(id=execution_id)
            crawl = WebPageCrawl.objects.get(execution=execution)
            
            # Perform crawling
            result = self.crawl_page(
                url=options['url'],
                follow_links=options['follow_links'],
                max_depth=options['max_depth']
            )
            
            # Update crawl data
            crawl.title = result['title']
            crawl.content = result['content']
            crawl.word_count = result['word_count']
            crawl.links_found = result['links']
            crawl.meta_data = result['meta']
            crawl.save()
            
            # Output structured result to stdout
            self.stdout.write(json.dumps(result))
            
        except Exception as e:
            # Log error to stderr
            self.stderr.write(f"Crawl failed: {str(e)}")
            # Output error result to stdout
            self.stdout.write(json.dumps({"error": str(e)}))
            sys.exit(1)

    def crawl_page(self, url, follow_links=False, max_depth=1):
        """Crawl a single page and extract content"""
        headers = {
            'User-Agent': 'Django Container Manager Demo Bot 1.0'
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract content
        title = soup.find('title')
        title_text = title.get_text().strip() if title else ''
        
        # Get main content (remove script/style tags)
        for script in soup(["script", "style"]):
            script.decompose()
        
        content = soup.get_text()
        content = ' '.join(content.split())  # Clean whitespace
        
        # Extract links
        links = []
        for link in soup.find_all('a', href=True):
            links.append({
                'url': link['href'],
                'text': link.get_text().strip()
            })
        
        # Extract meta information
        meta = {}
        for meta_tag in soup.find_all('meta'):
            name = meta_tag.get('name') or meta_tag.get('property')
            content = meta_tag.get('content')
            if name and content:
                meta[name] = content
        
        return {
            'title': title_text,
            'content': content,
            'word_count': len(content.split()),
            'links': links[:20],  # Limit to first 20 links
            'meta': meta,
            'url': url,
            'status_code': response.status_code
        }
```

## Workflow 2: Historical Figure Text Rewriter

### Purpose
Demonstrate AI/LLM integration with API key management and creative text transformation.

### Container Template Specification

```yaml
# Container configuration for text rewriter
name: "text-rewriter"
description: "Python environment for AI text processing with OpenAI/Anthropic APIs"
docker_image: "python:3.11-slim"
command: ["python", "manage.py", "rewrite_text"]
environment_variables_text: |
  DJANGO_SETTINGS_MODULE=demo_project.settings
  PYTHONPATH=/app
working_dir: "/app"
cpu_limit: 0.5
memory_limit_mb: 256
timeout_seconds: 180
```

### Management Command

```python
# demo_workflows/management/commands/rewrite_text.py
import json
import sys
from django.core.management.base import BaseCommand
from demo_workflows.models import WorkflowExecution, TextRewrite, DemoSettings

class Command(BaseCommand):
    help = 'Rewrite text in the style of a historical figure'

    def add_arguments(self, parser):
        parser.add_argument('execution_id', type=str, help='WorkflowExecution ID')
        parser.add_argument('--text', type=str, required=True, help='Text to rewrite')
        parser.add_argument('--figure', type=str, required=True, help='Historical figure')

    def handle(self, *args, **options):
        execution_id = options['execution_id']
        
        try:
            # Get workflow execution
            execution = WorkflowExecution.objects.get(id=execution_id)
            rewrite = TextRewrite.objects.get(execution=execution)
            
            # Get settings for API keys
            settings = DemoSettings.get_solo()
            
            # Perform rewriting
            result = self.rewrite_text(
                text=options['text'],
                figure=options['figure'],
                settings=settings
            )
            
            # Update rewrite data
            rewrite.rewritten_text = result['rewritten_text']
            rewrite.transformation_notes = result['notes']
            rewrite.model_used = result['model']
            rewrite.save()
            
            # Output structured result to stdout
            self.stdout.write(json.dumps(result))
            
        except Exception as e:
            self.stderr.write(f"Rewrite failed: {str(e)}")
            self.stdout.write(json.dumps({"error": str(e)}))
            sys.exit(1)

    def rewrite_text(self, text, figure, settings):
        """Rewrite text in the style of a historical figure"""
        
        # Figure style prompts
        figure_styles = {
            'shakespeare': "in the eloquent, poetic style of William Shakespeare with iambic pentameter and archaic English",
            'churchill': "in the powerful, inspiring rhetorical style of Winston Churchill with strong conviction",
            'lincoln': "in the humble, wise, and measured style of Abraham Lincoln with folksy metaphors",
            'einstein': "in the thoughtful, scientific style of Albert Einstein with curiosity and wonder",
            'twain': "in the witty, satirical style of Mark Twain with humor and folksy wisdom",
            'wilde': "in the witty, paradoxical style of Oscar Wilde with clever observations",
            'hemingway': "in the spare, direct style of Ernest Hemingway with understated emotion",
            'roosevelt': "in the vigorous, optimistic style of Theodore Roosevelt with bold enthusiasm",
        }
        
        style_description = figure_styles.get(figure, "in a distinctive historical style")
        
        prompt = f"""Rewrite the following text {style_description}. 
        Maintain the core meaning while transforming the voice, tone, and style:

        Original text: {text}

        Rewritten text:"""
        
        # Try OpenAI first, then Anthropic, then return mock response
        if settings.openai_api_key:
            result = self._use_openai(prompt, settings.openai_api_key)
            model = "OpenAI GPT"
        elif settings.anthropic_api_key:
            result = self._use_anthropic(prompt, settings.anthropic_api_key)
            model = "Anthropic Claude"
        else:
            result = self._mock_response(text, figure)
            model = "Mock (Demo Mode)"
        
        return {
            'rewritten_text': result,
            'notes': f"Transformed to {figure_styles.get(figure, 'historical')} style",
            'model': model,
            'original_text': text,
            'figure': figure
        }

    def _use_openai(self, prompt, api_key):
        """Use OpenAI API for text rewriting"""
        import openai
        
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500,
            temperature=0.8
        )
        return response.choices[0].message.content.strip()

    def _use_anthropic(self, prompt, api_key):
        """Use Anthropic API for text rewriting"""
        import anthropic
        
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.content[0].text.strip()

    def _mock_response(self, text, figure):
        """Generate mock response for demo when no API keys available"""
        transformations = {
            'shakespeare': f"Hark! {text} Verily, 'tis most wondrous indeed!",
            'churchill': f"We shall never surrender! {text} This is our finest hour!",
            'lincoln': f"As I have oft said, {text.lower()}. A house divided cannot stand.",
            'einstein': f"It is curious to observe that {text.lower()}. Imagination is more important than knowledge.",
            'twain': f"Well, I reckon {text.lower()}, though reports of its death may be greatly exaggerated.",
            'wilde': f"I can resist everything except temptation, and {text.lower()}. We are all in the gutter, but some of us are looking at the stars.",
            'hemingway': f"{text}. It was good.",
            'roosevelt': f"Bully! {text} Speak softly and carry a big stick!",
        }
        
        return transformations.get(figure, f"In the style of {figure}: {text}")
```

## Workflow 3: Document Analysis Pipeline

### Purpose
Demonstrate file processing, multi-step analysis, and comprehensive document intelligence.

### Container Template Specification

```yaml
# Container configuration for document analyzer
name: "document-analyzer"
description: "Python environment for document processing and AI analysis"
docker_image: "python:3.11-slim"
command: ["python", "manage.py", "analyze_document"]
environment_variables_text: |
  DJANGO_SETTINGS_MODULE=demo_project.settings
  PYTHONPATH=/app
working_dir: "/app"
cpu_limit: 1.0
memory_limit_mb: 512
timeout_seconds: 600
```

### Management Command

```python
# demo_workflows/management/commands/analyze_document.py
import json
import sys
import os
from pathlib import Path
from django.core.management.base import BaseCommand
from demo_workflows.models import WorkflowExecution, DocumentAnalysis

class Command(BaseCommand):
    help = 'Analyze a document and extract insights'

    def add_arguments(self, parser):
        parser.add_argument('execution_id', type=str, help='WorkflowExecution ID')
        parser.add_argument('--file-path', type=str, required=True, help='Path to document file')

    def handle(self, *args, **options):
        execution_id = options['execution_id']
        file_path = options['file_path']
        
        try:
            # Get workflow execution
            execution = WorkflowExecution.objects.get(id=execution_id)
            analysis = DocumentAnalysis.objects.get(execution=execution)
            
            # Perform analysis
            result = self.analyze_document(file_path)
            
            # Update analysis data
            analysis.text_content = result['text_content']
            analysis.word_count = result['word_count']
            analysis.page_count = result.get('page_count')
            analysis.sentiment_score = result.get('sentiment_score')
            analysis.summary = result.get('summary', '')
            analysis.key_topics = result.get('topics', [])
            analysis.entities = result.get('entities', [])
            analysis.save()
            
            # Output structured result to stdout
            self.stdout.write(json.dumps(result))
            
        except Exception as e:
            self.stderr.write(f"Analysis failed: {str(e)}")
            self.stdout.write(json.dumps({"error": str(e)}))
            sys.exit(1)

    def analyze_document(self, file_path):
        """Analyze document and extract insights"""
        
        # Extract text based on file type
        text_content = self._extract_text(file_path)
        
        # Basic analysis
        words = text_content.split()
        word_count = len(words)
        
        # Mock AI analysis (in real implementation, would use APIs)
        sentiment_score = self._analyze_sentiment(text_content)
        summary = self._generate_summary(text_content)
        topics = self._extract_topics(text_content)
        entities = self._extract_entities(text_content)
        
        return {
            'text_content': text_content[:5000],  # Truncate for storage
            'word_count': word_count,
            'page_count': self._estimate_pages(word_count),
            'sentiment_score': sentiment_score,
            'summary': summary,
            'topics': topics,
            'entities': entities,
            'file_path': file_path
        }

    def _extract_text(self, file_path):
        """Extract text from various file formats"""
        file_ext = Path(file_path).suffix.lower()
        
        if file_ext == '.pdf':
            return self._extract_pdf_text(file_path)
        elif file_ext in ['.txt', '.md']:
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

    def _extract_pdf_text(self, file_path):
        """Extract text from PDF file"""
        try:
            import PyPDF2
            
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
        except ImportError:
            return "PDF text extraction not available (PyPDF2 not installed)"

    def _analyze_sentiment(self, text):
        """Mock sentiment analysis (returns score between -1 and 1)"""
        # Simple word-based sentiment scoring for demo
        positive_words = ['good', 'great', 'excellent', 'amazing', 'wonderful', 'fantastic']
        negative_words = ['bad', 'terrible', 'awful', 'horrible', 'disappointing']
        
        words = text.lower().split()
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        if positive_count + negative_count == 0:
            return 0.0
        
        return (positive_count - negative_count) / (positive_count + negative_count)

    def _generate_summary(self, text):
        """Mock summary generation"""
        sentences = text.split('.')[:3]  # Take first 3 sentences
        return '. '.join(sentences).strip() + '.'

    def _extract_topics(self, text):
        """Mock topic extraction"""
        # Simple keyword-based topic extraction for demo
        topics = []
        word_freq = {}
        
        words = [word.lower().strip('.,!?') for word in text.split() if len(word) > 4]
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top 5 most frequent words as topics
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        topics = [word for word, count in sorted_words[:5] if count > 1]
        
        return topics

    def _extract_entities(self, text):
        """Mock entity extraction"""
        # Simple capitalized word extraction for demo
        import re
        
        # Find capitalized words (potential entities)
        entities = re.findall(r'\b[A-Z][a-z]+\b', text)
        
        # Remove common words and duplicates
        common_words = {'The', 'This', 'That', 'And', 'But', 'For', 'With'}
        entities = list(set([e for e in entities if e not in common_words]))
        
        return entities[:10]  # Return top 10

    def _estimate_pages(self, word_count):
        """Estimate page count based on word count"""
        return max(1, word_count // 250)  # ~250 words per page
```

## Container Templates and Jobs

### Integration with Container Manager

Each workflow creates a container job using the container manager:

```python
# Example workflow execution
def execute_workflow(workflow_execution):
    """Execute workflow using container manager"""
    from container_manager.models import ContainerTemplate, ContainerJob, ExecutorHost
    
    # Get template for workflow type
    template_map = {
        'crawler': 'web-page-crawler',
        'rewriter': 'text-rewriter',
        'analyzer': 'document-analyzer',
    }
    
    template_name = template_map[workflow_execution.workflow_type]
    template = ContainerTemplate.objects.get(name=template_name)
    
    # Get available executor host
    host = ExecutorHost.objects.filter(is_active=True).first()
    
    # Create container job
    container_job = ContainerJob.objects.create(
        name=f"{workflow_execution.workflow_type}-{workflow_execution.id}",
        template=template,
        executor_host=host,
        override_command=self._build_command(workflow_execution),
        status='pending'
    )
    
    # Link to workflow execution
    workflow_execution.container_job = container_job
    workflow_execution.save()
    
    return container_job

def _build_command(workflow_execution):
    """Build command arguments for each workflow type"""
    base_cmd = ["python", "manage.py"]
    
    if workflow_execution.workflow_type == 'crawler':
        crawl = workflow_execution.crawl_data
        return base_cmd + [
            "crawl_webpage", 
            str(workflow_execution.id),
            "--url", crawl.url
        ]
    elif workflow_execution.workflow_type == 'rewriter':
        rewrite = workflow_execution.rewrite_data
        return base_cmd + [
            "rewrite_text",
            str(workflow_execution.id),
            "--text", rewrite.original_text,
            "--figure", rewrite.historical_figure
        ]
    elif workflow_execution.workflow_type == 'analyzer':
        analysis = workflow_execution.analysis_data
        return base_cmd + [
            "analyze_document",
            str(workflow_execution.id),
            "--file-path", analysis.document_file.path
        ]
```

## Output Standards

### Structured JSON Output

All commands output JSON to stdout for easy parsing:

```json
{
  "success": true,
  "data": {
    "title": "Example Page",
    "content": "Page content...",
    "word_count": 150
  },
  "metadata": {
    "execution_time": 2.5,
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

### Error Handling

Errors are logged to stderr and also output as JSON:

```json
{
  "success": false,
  "error": "Connection timeout",
  "error_type": "NetworkError",
  "metadata": {
    "timestamp": "2024-01-15T10:30:00Z"
  }
}
```

This specification provides a comprehensive foundation for implementing three distinct, practical workflows that demonstrate the container manager's capabilities while showcasing modern development patterns.