/**
 * Layer 2 Connector for ARGO Layer 1
 * Provides communication interface with Python-based Layer 2
 */

import { EventEmitter } from 'events';
import { readFile, writeFile, mkdir } from 'fs/promises';
import { existsSync } from 'fs';
import { join } from 'path';

interface Layer2Message {
  id: string;
  timestamp: string;
  source: 'layer1';
  target: 'layer2';
  event_type: string;
  data: any;
}

interface Layer2Response {
  id: string;
  timestamp: string;
  source: 'layer2';
  target: 'layer1';
  event_type: string;
  data: any;
  correlation_id?: string;
}

export class Layer2Connector extends EventEmitter {
  private dataDir: string;
  private layer1ToLayer2Dir: string;
  private layer2ToLayer1Dir: string;
  private syncInterval: NodeJS.Timeout | null = null;
  private isRunning: boolean = false;

  constructor(dataDir: string = 'C:\\Argo-813\\data') {
    super();
    this.dataDir = dataDir;
    this.layer1ToLayer2Dir = join(dataDir, 'layer1_to_layer2');
    this.layer2ToLayer1Dir = join(dataDir, 'layer2_to_layer1');
    
    this.initializeDirectories();
  }

  private async initializeDirectories(): Promise<void> {
    try {
      if (!existsSync(this.dataDir)) {
        await mkdir(this.dataDir, { recursive: true });
      }
      if (!existsSync(this.layer1ToLayer2Dir)) {
        await mkdir(this.layer1ToLayer2Dir, { recursive: true });
      }
      if (!existsSync(this.layer2ToLayer1Dir)) {
        await mkdir(this.layer2ToLayer1Dir, { recursive: true });
      }
    } catch (error) {
      console.error('Failed to initialize directories:', error);
    }
  }

  /**
   * Start the connector service
   */
  async start(): Promise<void> {
    if (this.isRunning) {
      console.log('Layer2Connector is already running');
      return;
    }

    console.log('🚀 Starting Layer 2 Connector...');
    this.isRunning = true;

    // Start polling for responses from Layer 2
    this.syncInterval = setInterval(async () => {
      await this.checkForResponses();
    }, 100); // Check every 100ms

    console.log('✅ Layer 2 Connector started');
  }

  /**
   * Stop the connector service
   */
  async stop(): Promise<void> {
    if (!this.isRunning) {
      return;
    }

    console.log('🛑 Stopping Layer 2 Connector...');
    this.isRunning = false;

    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }

    console.log('✅ Layer 2 Connector stopped');
  }

  /**
   * Send message to Layer 2
   */
  async sendToLayer2(eventType: string, data: any): Promise<string> {
    const message: Layer2Message = {
      id: `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      source: 'layer1',
      target: 'layer2',
      event_type: eventType,
      data
    };

    try {
      const messagePath = join(this.layer1ToLayer2Dir, `${message.id}.json`);
      await writeFile(messagePath, JSON.stringify(message, null, 2));
      
      console.log(`📤 Sent to Layer 2: ${eventType} (${message.id})`);
      
      // Emit event for local listeners
      this.emit('message_sent', message);
      
      return message.id;
    } catch (error) {
      console.error('Failed to send message to Layer 2:', error);
      throw error;
    }
  }

  /**
   * Check for responses from Layer 2
   */
  private async checkForResponses(): Promise<void> {
    try {
      const files = await this.getResponseFiles();
      
      for (const file of files) {
        try {
          const response = await this.readResponseFile(file);
          if (response) {
            await this.processResponse(response);
            await this.deleteResponseFile(file);
          }
        } catch (error) {
          console.error(`Error processing response file ${file}:`, error);
        }
      }
    } catch (error) {
      console.error('Error checking for responses:', error);
    }
  }

  /**
   * Get list of response files from Layer 2
   */
  private async getResponseFiles(): Promise<string[]> {
    try {
      const { readdir } = await import('fs/promises');
      const files = await readdir(this.layer2ToLayer1Dir, { withFileTypes: true });
      return files
        .filter(file => file.isFile() && file.name.endsWith('.json'))
        .map(file => file.name);
    } catch (error) {
      return [];
    }
  }

  /**
   * Read response file from Layer 2
   */
  private async readResponseFile(filename: string): Promise<Layer2Response | null> {
    try {
      const filePath = join(this.layer2ToLayer1Dir, filename);
      const content = await readFile(filePath, 'utf-8');
      return JSON.parse(content) as Layer2Response;
    } catch (error) {
      console.error(`Error reading response file ${filename}:`, error);
      return null;
    }
  }

  /**
   * Process response from Layer 2
   */
  private async processResponse(response: Layer2Response): Promise<void> {
    console.log(`📥 Received from Layer 2: ${response.event_type} (${response.id})`);
    
    // Emit event for local listeners
    this.emit('message_received', response);
    
    // Emit specific event type
    this.emit(response.event_type, response.data, response);
  }

  /**
   * Delete response file after processing
   */
  private async deleteResponseFile(filename: string): Promise<void> {
    try {
      const filePath = join(this.layer2ToLayer1Dir, filename);
      await writeFile(filePath, ''); // Clear file content
    } catch (error) {
      console.error(`Error deleting response file ${filename}:`, error);
    }
  }

  /**
   * Get connector status
   */
  getStatus(): any {
    return {
      status: this.isRunning ? 'active' : 'stopped',
      dataDir: this.dataDir,
      layer1ToLayer2Dir: this.layer1ToLayer2Dir,
      layer2ToLayer1Dir: this.layer2ToLayer1Dir,
      isRunning: this.isRunning
    };
  }

  /**
   * Clear all message files (for testing)
   */
  async clearMessages(): Promise<void> {
    try {
      // Clear Layer 1 → Layer 2 messages
      const outFiles = await this.getOutgoingFiles();
      for (const file of outFiles) {
        await this.deleteOutgoingFile(file);
      }

      // Clear Layer 2 → Layer 1 responses
      const responseFiles = await this.getResponseFiles();
      for (const file of responseFiles) {
        await this.deleteResponseFile(file);
      }

      console.log('🧹 All message files cleared');
    } catch (error) {
      console.error('Error clearing messages:', error);
    }
  }

  private async getOutgoingFiles(): Promise<string[]> {
    try {
      const { readdir } = await import('fs/promises');
      const files = await readdir(this.layer1ToLayer2Dir, { withFileTypes: true });
      return files
        .filter(file => file.isFile() && file.name.endsWith('.json'))
        .map(file => file.name);
    } catch (error) {
      return [];
    }
  }

  private async deleteOutgoingFile(filename: string): Promise<void> {
    try {
      const filePath = join(this.layer1ToLayer2Dir, filename);
      await writeFile(filePath, ''); // Clear file content
    } catch (error) {
      console.error(`Error deleting outgoing file ${filename}:`, error);
    }
  }
}

// Export singleton instance
export const layer2Connector = new Layer2Connector();
