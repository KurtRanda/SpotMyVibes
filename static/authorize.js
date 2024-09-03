const clientId = '145d25fd21e4441fa2c343749071f82c';
const redirectUri = 'http://localhost:5000/callback';
const scope = 'user-read-private user-read-email';
const authUrl = new URL("https://accounts.spotify.com/authorize");

// generated in the previous step
window.localStorage.setItem('code_verifier', codeVerifier);

const params =  {
  response_type: 'code',
  client_id: clientId,
  scope,
  code_challenge_method: 'S256',
  code_challenge: codeChallenge,
  redirect_uri: redirectUri,
};

authUrl.search = new URLSearchParams(params).toString();
window.location.href = authUrl.toString();
