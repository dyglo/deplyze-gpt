# Firebase Email Verification Template

Firebase Console path:

Authentication -> Templates -> Email address verification

## Action URL

Set the custom action URL to:

```text
https://deplyzegpt.xyz/verified
```

Firebase appends `mode` and `oobCode` to this URL. The React `/verified` route applies the verification code and then renders the branded confirmation page.

## Subject

```text
Verify your email for DeplyzeGPT
```

## HTML body

Paste this into the custom email template field:

```html
<div style="margin:0;padding:0;background:#111111;color:#F5F4EF;font-family:Inter,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#111111;margin:0;padding:0;">
    <tr>
      <td align="center" style="padding:40px 20px;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="max-width:560px;margin:0 auto;">
          <tr>
            <td style="padding:0 0 28px 0;">
              <div style="font-size:22px;line-height:1.2;font-weight:700;color:#F5F4EF;letter-spacing:0;">
                DeplyzeGPT
              </div>
            </td>
          </tr>
          <tr>
            <td style="border:1px solid #2A2927;background:#181818;border-radius:8px;padding:32px;">
              <div style="width:42px;height:42px;border-radius:8px;background:#2A1A10;color:#C96A2A;text-align:center;line-height:42px;font-size:24px;margin:0 0 22px 0;">
                *
              </div>
              <h1 style="margin:0 0 14px 0;font-size:28px;line-height:1.2;font-weight:700;color:#F5F4EF;letter-spacing:0;">
                Verify your email
              </h1>
              <p style="margin:0 0 24px 0;font-size:15px;line-height:1.6;color:#C9C7C2;">
                Confirm this email address to finish setting up your DeplyzeGPT account.
              </p>
              <a href="%LINK%" style="display:inline-block;background:#C96A2A;color:#FFFFFF;text-decoration:none;border-radius:8px;padding:13px 20px;font-size:14px;line-height:1;font-weight:700;">
                Verify My Email
              </a>
              <p style="margin:24px 0 0 0;font-size:13px;line-height:1.6;color:#8F8D88;">
                If the button does not work, copy and paste this link into your browser:<br>
                <a href="%LINK%" style="color:#C96A2A;text-decoration:underline;word-break:break-all;">%LINK%</a>
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:22px 0 0 0;">
              <p style="margin:0;font-size:12px;line-height:1.6;color:#8F8D88;">
                If you didn't create a DeplyzeGPT account, you can safely ignore this email.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</div>
```
