# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Retrieval-Augmented Generation (RAG) based intelligent troubleshooting assistant for Session Border Controller (SBC) systems. The system helps users understand SBC-related protocols and diagnose faults by:

1. **Protocol Query**: Answering questions about SBC protocols, standards (like SIP, RFCs), and definitions
2. **Fault Diagnosis**: Troubleshooting SBC-related issues through structured diagnosis with tools

## Key Components

- `main.py` - Main application entry point and user interface
- `router.py` - Query routing system
- `rag.py` - Core RAG system (ChromaDB backend, batch processing, breakpoint resume)
- `agent.py` - LLM agent for fault diagnosis with tool calling
- `tools.py` - Diagnostic tools for SBC systems
- `chunker.py` - Document chunking (RFCChunker + GPPChunker)
- `document_loader.py` - Document processing with meta-data handling
- `config.py` - System configuration and API management
- `query_expander.py` - Query expansion with rule-based + LLM modes
- `logger_config.py` - Logging configuration
- `rfc_loader.py` - RFC document download and processing
- `3gpp_pdf_loader.py` - 3GPP PDF processing with Docling

## Architecture

1. **User Input** → **Query Router** → **Route to appropriate system**
   - Protocol queries → RAG system → LLM
   - Fault diagnosis → Agent system → RAG system → Tools → LLM

2. **Vector Storage**: ChromaDB with automatic persistence

## Directory Structure

- `knowledge_base/` - Markdown documents
- `kb_store/chroma_db/` - Persisted ChromaDB knowledge base
- `model_files/` - Local embedding/reranking models
- `logs/` - Log output directory
