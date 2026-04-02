from dataclasses import replace
from pyexpat.errors import messages
from OrgAuth.templates.EmailTemplates import EmailTemplates


class TemplateManagementEngine:
    def replace_tags(self, template_string, **kwargs):
        try:
            for k, v in kwargs.items():
                template_string = template_string.replace("[%s]" % str(k), str(v))
            return template_string
        except Exception as e:
            print("replace_tags Exception: %s", e)
        return template_string

    def createOtpEmail(self, **kwargs):
        """OTP verification email"""
        return EmailTemplates.otp(**kwargs)

    def createCorporateEmail(self, **kwargs):
        """Corporate creation email - delegates to EmailTemplates"""
        return EmailTemplates.corporate_created(**kwargs)

    def createCorporateApprovalEmail(self, **kwargs):
        """Corporate approval email - delegates to EmailTemplates"""
        return EmailTemplates.corporate_approval(**kwargs)
    
    def createCorporateDisapprovalEmail(self, **kwargs):
        """Corporate disapproval email - delegates to EmailTemplates"""
        return EmailTemplates.corporate_disapproval(**kwargs)
    
    def createCorporateSuspendedEmail(self, **kwargs):
        """Corporate suspension email - delegates to EmailTemplates"""
        return EmailTemplates.corporate_suspended(**kwargs)
    
    def createCorporateProfileUpdatedEmail(self, **kwargs):
        """Corporate profile update email - delegates to EmailTemplates"""
        return EmailTemplates.corporate_profile_updated(**kwargs)
    
    def createCorporateDeletedEmail(self, **kwargs):
        """Corporate deletion email - delegates to EmailTemplates"""
        return EmailTemplates.corporate_deleted(**kwargs)
    
    def createUserWelcomeEmail(self, **kwargs):
        """User welcome email with credentials - delegates to EmailTemplates"""
        return EmailTemplates.user_welcome(**kwargs)
    
    def createUserDeletedEmail(self, **kwargs):
        """User deletion email - delegates to EmailTemplates"""
        return EmailTemplates.user_deleted(**kwargs)
    
    def createUserUpdatedEmail(self, **kwargs):
        """User profile update email - delegates to EmailTemplates"""
        return EmailTemplates.user_updated(**kwargs)
    
    def createUserSuspendedEmail(self, **kwargs):
        """User suspension email - delegates to EmailTemplates"""
        return EmailTemplates.user_suspended(**kwargs)
    
    def createUserUnsuspendedEmail(self, **kwargs):
        """User reactivation email - delegates to EmailTemplates"""
        return EmailTemplates.user_unsuspended(**kwargs)
    
    def createIndividualActivationEmail(self, **kwargs):
        """Individual user activation email - delegates to EmailTemplates"""
        return EmailTemplates.individual_activation(**kwargs)
    
    def createIndividualActivationResendEmail(self, **kwargs):
        """Individual activation resend email - delegates to EmailTemplates"""
        return EmailTemplates.individual_activation_resend(**kwargs)
    
    def createIndividualActivatedEmail(self, **kwargs):
        """Individual account activated email - delegates to EmailTemplates"""
        return EmailTemplates.individual_activated(**kwargs)
