console.log('JavaScript is connected!');

// JavaScript code to generate a code verifier and code challenge

const generateRandomString = (length) => {
    const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    const values = crypto.getRandomValues(new Uint8Array(length));
    return values.reduce((acc, x) => acc + possible[x % possible.length], "");
  }
  
  const sha256 = async (plain) => {
    const encoder = new TextEncoder();
    const data = encoder.encode(plain);
    return window.crypto.subtle.digest('SHA-256', data);
  }
  
  const base64encode = (input) => {
    return btoa(String.fromCharCode(...new Uint8Array(input)))
      .replace(/=/g, '')
      .replace(/\+/g, '-')
      .replace(/\//g, '_');
  }
  
  const createCodeChallenge = async (verifier) => {
    const hashed = await sha256(verifier);
    return base64encode(hashed);
  }
  
  const codeVerifier = generateRandomString(64);
  const codeChallenge = await createCodeChallenge(codeVerifier);
  
  // Save the code verifier in localStorage for later use
  window.localStorage.setItem('code_verifier', codeVerifier);
  
  // Now you can proceed to the authorization step
  