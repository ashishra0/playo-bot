const { Client, LocalAuth } = require('whatsapp-web.js');
const express = require('express');
const axios = require('axios');
const qrcode = require('qrcode-terminal');

const BOT_INCOMING_URL = process.env.BOT_INCOMING_URL || 'http://bot:5000/wa-incoming';
const PORT = 3000;

const app = express();
app.use(express.json());

const client = new Client({
    authStrategy: new LocalAuth({ dataPath: '/app/.wwebjs_auth' }),
    puppeteer: {
        executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium',
        args: [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
        ],
    },
});

client.on('qr', (qr) => {
    console.log('Scan this QR code with WhatsApp:');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('WhatsApp client ready');
});

client.on('disconnected', (reason) => {
    console.log('WhatsApp disconnected:', reason);
});

// Forward all /find messages (sent or received) to the Python bot
client.on('message_create', async (msg) => {
    if (!msg.body || !msg.body.trim().toLowerCase().startsWith('/find')) return;

    try {
        const chat = await msg.getChat();
        const chatId = chat.id._serialized;

        await axios.post(BOT_INCOMING_URL, {
            chatId,
            senderName: msg._data.notifyName || 'Someone',
            text: msg.body.trim(),
        });
    } catch (e) {
        console.error('Failed to forward message to bot:', e.message);
    }
});

// Send a message — called by the Python bot
app.post('/send', async (req, res) => {
    const { chatId, message } = req.body;
    if (!chatId || !message) {
        return res.status(400).json({ error: 'chatId and message are required' });
    }
    try {
        await client.sendMessage(chatId, message);
        res.json({ success: true });
    } catch (e) {
        console.error('Send failed:', e.message);
        res.status(500).json({ error: e.message });
    }
});

// Health check
app.get('/health', (req, res) => {
    res.json({ status: client.info ? 'ready' : 'not_ready' });
});

app.listen(PORT, () => console.log(`WhatsApp service listening on port ${PORT}`));
client.initialize();
