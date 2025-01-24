# React Authenticator App

A TOTP (Time-based One-Time Password) generator implementation using React.

## Features
- Add/Remove authentication accounts
- Real-time code generation
- 30-second countdown timer
- Copy to clipboard functionality
- Local storage persistence

## Setup
1. Install dependencies:
```bash
npm install otplib react-icons
```

2. Start development server:
```bash
npm start
```

## Usage
1. Add new account:
   - Provide account name
   - Enter base32 secret key
   
2. Test with sample secret:
   ```
   JBSWY3DPEHPK3PXP
   ```
   (Generates same codes as 'JBSWY3DPEHPK3PXP' test pattern)

3. Codes automatically refresh every 30 seconds
