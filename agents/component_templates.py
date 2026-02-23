"""
DrupalMind - Component Templates
Template library for Drupal component generation.
7 proven templates: hero, grid, testimonial, content block, blog post, team member, features
"""
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class ComponentTemplate:
    """Base class for component templates."""
    
    def __init__(self, template_id: str, name: str, description: str):
        self.template_id = template_id
        self.name = name
        self.description = description
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate required fields.
        
        Returns:
            (is_valid, error_list)
        """
        raise NotImplementedError
    
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render Drupal JSON:API payload.
        
        Returns:
            Dict with node payload
        """
        raise NotImplementedError


class HeroBasicTemplate(ComponentTemplate):
    """Hero section with heading, tagline, CTA."""
    
    def __init__(self):
        super().__init__(
            template_id="hero_basic",
            name="Hero Basic",
            description="Hero sections with heading, tagline, CTA button"
        )
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        if not data.get("heading"):
            errors.append("heading is required")
        if not data.get("tagline"):
            errors.append("tagline is required")
        return len(errors) == 0, errors
    
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        heading = data.get("heading", "")
        tagline = data.get("tagline", "")
        cta_text = data.get("cta_text", "Learn More")
        cta_url = data.get("cta_url", "#")
        primary_color = data.get("primary_color", "#1a1a2e")
        secondary_color = data.get("secondary_color", "#e94560")
        
        body_html = f"""
<div class="hero-section" style="background: linear-gradient(135deg, {primary_color}, {secondary_color}); padding: 60px 20px; text-align: center; color: white;">
    <h1 style="font-size: 2.5em; margin-bottom: 16px;">{heading}</h1>
    <p style="font-size: 1.2em; margin-bottom: 24px; opacity: 0.9;">{tagline}</p>
    <a href="{cta_url}" style="display: inline-block; padding: 12px 32px; background: {secondary_color}; color: white; text-decoration: none; border-radius: 4px; font-weight: 600;">{cta_text}</a>
</div>
"""
        return {
            "data": {
                "type": "node--page",
                "attributes": {
                    "title": heading,
                    "body": {
                        "value": body_html,
                        "format": "basic_html"
                    }
                }
            }
        }


class FeaturesGridTemplate(ComponentTemplate):
    """Features grid with 3+ columns."""
    
    def __init__(self):
        super().__init__(
            template_id="features_grid",
            name="Features Grid",
            description="Feature grids with 3+ columns"
        )
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        if not data.get("title"):
            errors.append("title is required")
        features = data.get("features", [])
        if not features:
            errors.append("features list is required")
        return len(errors) == 0, errors
    
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        title = data.get("title", "Features")
        features = data.get("features", [])
        
        features_html = '<div class="features-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 24px; padding: 40px 20px;">'
        
        for feature in features:
            icon = feature.get("icon", "★")
            feature_title = feature.get("title", "")
            description = feature.get("description", "")
            
            features_html += f"""
<div class="feature-item" style="text-align: center; padding: 20px;">
    <div style="font-size: 2em; margin-bottom: 12px;">{icon}</div>
    <h3 style="margin-bottom: 8px;">{feature_title}</h3>
    <p style="color: #666;">{description}</p>
</div>
"""
        
        features_html += "</div>"
        
        body_html = f"""
<h2>{title}</h2>
{features_html}
"""
        return {
            "data": {
                "type": "node--page",
                "attributes": {
                    "title": title,
                    "body": {
                        "value": body_html,
                        "format": "basic_html"
                    }
                }
            }
        }


class BlogPostTemplate(ComponentTemplate):
    """Blog article with metadata."""
    
    def __init__(self):
        super().__init__(
            template_id="blog_post",
            name="Blog Post",
            description="Blog articles with metadata"
        )
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        if not data.get("title"):
            errors.append("title is required")
        if not data.get("content"):
            errors.append("content is required")
        return len(errors) == 0, errors
    
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        title = data.get("title", "")
        content = data.get("content", "")
        author = data.get("author", "DrupalMind")
        date = data.get("date", "")
        category = data.get("category", "")
        
        body_html = f"""
<article class="blog-post" style="max-width: 800px; margin: 0 auto; padding: 40px 20px;">
    <header style="margin-bottom: 24px; border-bottom: 1px solid #eee; padding-bottom: 16px;">
        <h1 style="font-size: 2em; margin-bottom: 12px;">{title}</h1>
        <div style="color: #666; font-size: 0.9em;">
            <span>By {author}</span>
            {" - " + date if date else ""}
            {" - " + category if category else ""}
        </div>
    </header>
    <div class="content" style="line-height: 1.8;">
        {content}
    </div>
</article>
"""
        return {
            "data": {
                "type": "node--article",
                "attributes": {
                    "title": title,
                    "body": {
                        "value": body_html,
                        "format": "basic_html"
                    }
                }
            }
        }


class TestimonialCardTemplate(ComponentTemplate):
    """Testimonial quote card."""
    
    def __init__(self):
        super().__init__(
            template_id="testimonial_card",
            name="Testimonial Card",
            description="Testimonial quotes"
        )
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        if not data.get("quote"):
            errors.append("quote is required")
        if not data.get("author"):
            errors.append("author is required")
        return len(errors) == 0, errors
    
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        quote = data.get("quote", "")
        author = data.get("author", "")
        role = data.get("role", "")
        avatar = data.get("avatar", "")
        
        avatar_html = f'<img src="{avatar}" alt="{author}" style="width: 60px; height: 60px; border-radius: 50%; margin-right: 16px;"' if avatar else ""
        
        body_html = f"""
<div class="testimonial" style="background: #f9f9f9; padding: 24px; border-radius: 8px; margin: 20px 0;">
    <blockquote style="font-size: 1.1em; font-style: italic; margin: 0 0 16px 0;">
        "{quote}"
    </blockquote>
    <div style="display: flex; align-items: center;">
        {avatar_html}
        <div>
            <strong>{author}</strong>
            {"<br><span style='color: #666;'>" + role + "</span>" if role else ""}
        </div>
    </div>
</div>
"""
        return {
            "data": {
                "type": "node--page",
                "attributes": {
                    "title": f"Testimonial: {author}",
                    "body": {
                        "value": body_html,
                        "format": "basic_html"
                    }
                }
            }
        }


class TeamMemberTemplate(ComponentTemplate):
    """Team member profile."""
    
    def __init__(self):
        super().__init__(
            template_id="team_member",
            name="Team Member",
            description="Team member profiles"
        )
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        if not data.get("name"):
            errors.append("name is required")
        return len(errors) == 0, errors
    
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        name = data.get("name", "")
        role = data.get("role", "")
        bio = data.get("bio", "")
        photo = data.get("photo", "")
        social = data.get("social", {})
        
        photo_html = f'<img src="{photo}" alt="{name}" style="width: 120px; height: 120px; border-radius: 50%; object-fit: cover; margin-bottom: 16px;"' if photo else ""
        
        social_html = ""
        if social:
            social_html = '<div style="margin-top: 12px;">'
            for platform, url in social.items():
                social_html += f'<a href="{url}" style="margin-right: 8px;">{platform}</a>'
            social_html += '</div>'
        
        body_html = f"""
<div class="team-member" style="text-align: center; padding: 24px; border: 1px solid #eee; border-radius: 8px;">
    {photo_html}
    <h3 style="margin-bottom: 4px;">{name}</h3>
    <p style="color: #666; margin-bottom: 12px;">{role}</p>
    <p style="font-size: 0.9em;">{bio}</p>
    {social_html}
</div>
"""
        return {
            "data": {
                "type": "node--page",
                "attributes": {
                    "title": f"Team: {name}",
                    "body": {
                        "value": body_html,
                        "format": "basic_html"
                    }
                }
            }
        }


class ContentBlockTemplate(ComponentTemplate):
    """Generic content section."""
    
    def __init__(self):
        super().__init__(
            template_id="content_block",
            name="Content Block",
            description="Generic content sections"
        )
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        if not data.get("title"):
            errors.append("title is required")
        return len(errors) == 0, errors
    
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        title = data.get("title", "")
        content = data.get("content", "")
        background = data.get("background", "#ffffff")
        
        body_html = f"""
<div class="content-block" style="padding: 40px 20px; background: {background};">
    <h2 style="margin-bottom: 16px;">{title}</h2>
    <div style="line-height: 1.6;">{content}</div>
</div>
"""
        return {
            "data": {
                "type": "node--page",
                "attributes": {
                    "title": title,
                    "body": {
                        "value": body_html,
                        "format": "basic_html"
                    }
                }
            }
        }


class FeaturesTemplate(ComponentTemplate):
    """Features list section."""
    
    def __init__(self):
        super().__init__(
            template_id="features",
            name="Features",
            description="Feature list with icons"
        )
    
    def validate(self, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        if not data.get("title"):
            errors.append("title is required")
        return len(errors) == 0, errors
    
    def render(self, data: Dict[str, Any]) -> Dict[str, Any]:
        title = data.get("title", "")
        items = data.get("items", [])
        
        items_html = '<ul style="list-style: none; padding: 0;">'
        
        for item in items:
            icon = item.get("icon", "✓")
            text = item.get("text", "")
            items_html += f'<li style="padding: 8px 0;"><span style="margin-right: 8px;">{icon}</span>{text}</li>'
        
        items_html += '</ul>'
        
        body_html = f"""
<h2>{title}</h2>
{items_html}
"""
        return {
            "data": {
                "type": "node--page",
                "attributes": {
                    "title": title,
                    "body": {
                        "value": body_html,
                        "format": "basic_html"
                    }
                }
            }
        }


class TemplateLibrary:
    """Library of component templates."""
    
    def __init__(self):
        self.templates: Dict[str, ComponentTemplate] = {}
        self._register_default_templates()
    
    def _register_default_templates(self):
        """Register the 7 default templates."""
        self.templates["hero_basic"] = HeroBasicTemplate()
        self.templates["features_grid"] = FeaturesGridTemplate()
        self.templates["blog_post"] = BlogPostTemplate()
        self.templates["testimonial_card"] = TestimonialCardTemplate()
        self.templates["team_member"] = TeamMemberTemplate()
        self.templates["content_block"] = ContentBlockTemplate()
        self.templates["features"] = FeaturesTemplate()
    
    def get_template(self, template_id: str) -> Optional[ComponentTemplate]:
        """Get a template by ID."""
        return self.templates.get(template_id)
    
    def list_templates(self) -> List[Dict[str, str]]:
        """List all available templates."""
        return [
            {
                "id": t.template_id,
                "name": t.name,
                "description": t.description
            }
            for t in self.templates.values()
        ]
    
    def render_with_fallback(self, template_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render with fallback to content_block if template not found.
        
        Returns:
            rendered_payload as Dict
        """
        template = self.get_template(template_id)
        
        if not template:
            logger.warning(f"Template {template_id} not found, using content_block fallback")
            template = self.get_template("content_block")
            # Ensure title is set for fallback
            if "title" not in data:
                data["title"] = "Content"
        
        if template:
            return template.render(data)
        return {"error": "No template available"}
    
    def validate_template_data(self, template_id: str, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate data for a template."""
        template = self.get_template(template_id)
        if not template:
            return False, [f"Template {template_id} not found"]
        return template.validate(data)


# Factory function
def create_template_library() -> TemplateLibrary:
    """Create and return a template library instance."""
    return TemplateLibrary()


# Convenience function for quick template rendering
def render_component(template_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Quick function to render a component."""
    library = create_template_library()
    return library.render_with_fallback(template_id, data)
