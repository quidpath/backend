from dataclasses import replace

from pyexpat.errors import messages


class TemplateManagementEngine:
    def replace_tags(self, template_string, **kwargs):
        """
        Replaces all the occurrences of replace tags with the passed in arguments.
        @param template_string: The template string we are supposed to replace tags.
        @type template_string: str
        @param kwargs: The key->word arguments representing the tags in the string without []
        @return: The template string replaced accordingly.
        @rtype: str
        """
        try:
            for k, v in kwargs.items():
                template_string = template_string.replace('[%s]' % str(k), str(v))
            return template_string
        except Exception as e:
            print('replace_tags Exception: %s', e)
        return template_string

    def createCorporateEmail(self, **kwargs):
        message=\
        """
        <html>
  <head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
    <style>
      body {
        font-family: Arial, sans-serif;
        background-color: #f1fdf3;
        margin: 0;
        padding: 0;
      }
      .container {
        max-width: 600px;
        margin: 40px auto;
        padding: 0;
        background-color: #ffffff;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
      }
      .header {
        background-color: #a7c0ba; /* Dark green */
        padding: 20px;
        text-align: center;
      }
      .header img {
        max-width: 150px;
        height: auto;
      }
      .content {
        padding: 30px;
        background-color: #ffffff;
      }
      .content h1 {
        color: #064e3b;
        margin-bottom: 10px;
      }
      .content p {
        color: #333333;
        line-height: 1.6;
        font-size: 16px;
      }
      .footer {
        background-color: #d1fae5; /* Light green */
        padding: 15px;
        text-align: center;
        font-size: 13px;
        color: #065f46;
      }
    </style>
  </head>
  <body>
    <div class="container">
      <div class="header">
        <h1>Welcome</>
      </div>
      <div class="content">
        <h1>Organization Created</h1>
        <p>Dear <strong>[corporate_name]</strong>,</p>
        <p>Your application has been successfully submitted. We are currently reviewing your request.</p>
        <p>You will receive a confirmation email once your organization is approved.</p>
        <p>Thank you for choosing our platform!</p>
      </div>
      <div class="footer">
        &copy; @2025 quidpath. All rights reserved.
      </div>
    </div>
  </body>
</html>

        """
        return self.replace_tags(message, **kwargs)