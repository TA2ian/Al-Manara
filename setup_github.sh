#!/bin/bash
# سكريبت إعداد GitHub تلقائي

set -e

echo "🚀 بدء إعداد البوت على GitHub..."
echo ""

# ===== الخطوة 1: التحقق من المتطلبات =====
echo "📋 الخطوة 1: التحقق من المتطلبات..."

if ! command -v git &> /dev/null; then
    echo "❌ git غير مثبت. يرجى تثبيته أولاً:"
    echo "   Ubuntu/Debian: sudo apt install git"
    echo "   macOS: brew install git"
    exit 1
fi

if ! command -v gh &> /dev/null; then
    echo "❌ GitHub CLI (gh) غير مثبت. يرجى تثبيته:"
    echo "   https://cli.github.com/"
    exit 1
fi

echo "✅ جميع المتطلبات متوفرة"
echo ""

# ===== الخطوة 2: تسجيل الدخول لـ GitHub =====
echo "📋 الخطوة 2: التحقق من تسجيل الدخول..."

if ! gh auth status &> /dev/null; then
    echo "🔐 يرجى تسجيل الدخول إلى GitHub:"
    gh auth login
fi

echo "✅ مسجل الدخول إلى GitHub"
echo ""

# ===== الخطوة 3: إنشاء المستودع =====
echo "📋 الخطوة 3: إنشاء مستودع GitHub..."

cd "$(dirname "$0")"

# اسم المستودع
read -p "أدخل اسم المستودع (افتراضي: crypto-topup-bot): " REPO_NAME
REPO_NAME=${REPO_NAME:-crypto-topup-bot}

# التحقق من عدم وجود المستودع
if gh repo view "$REPO_NAME" &> /dev/null; then
    echo "⚠️ المستودع موجود بالفعل. هل تريد المتابعة؟ (y/n)"
    read -r CONTINUE
    if [ "$CONTINUE" != "y" ]; then
        exit 0
    fi
else
    # إنشاء المستودع
    read -p "عام (public) أم خاص (private)؟ [public/private]: " VISIBILITY
    VISIBILITY=${VISIBILITY:-public}

    gh repo create "$REPO_NAME" --"$VISIBILITY" --source=. --push
    echo "✅ تم إنشاء المستودع: https://github.com/$(gh api user -q .login)/$REPO_NAME"
fi

echo ""

# ===== الخطوة 4: إعداد Git =====
echo "📋 الخطوة 4: إعداد Git..."

if [ ! -d ".git" ]; then
    git init
    git branch -M main
fi

git add .
git commit -m "🚀 Initial commit: Crypto Top-Up Bot v1.0" || true

# ربط المستودع البعيد
REMOTE_URL="https://github.com/$(gh api user -q .login)/$REPO_NAME.git"
git remote remove origin 2>/dev/null || true
git remote add origin "$REMOTE_URL"

echo "✅ تم إعداد Git"
echo ""

# ===== الخطوة 5: رفع الملفات =====
echo "📋 الخطوة 5: رفع الملفات..."

git push -u origin main || {
    echo "⚠️ فشل الرفع. محاولة الدمج..."
    git pull origin main --rebase
    git push -u origin main
}

echo "✅ تم رفع الملفات بنجاح!"
echo ""

# ===== الخطوة 6: عرض المعلومات =====
echo "=========================================="
echo "🎉 تم الإعداد بنجاح!"
echo "=========================================="
echo ""
echo "🔗 رابط المستودع:"
echo "   $REMOTE_URL"
echo ""
echo "📋 الخطوات التالية:"
echo "   1. سجل في https://render.com"
echo "   2. اربط حساب GitHub"
echo "   3. New → PostgreSQL → Free"
echo "   4. New → Web Service → اختر المستودع"
echo "   5. اختر Docker كـ Runtime"
echo "   6. أضف متغيرات البيئة:"
echo "      - BOT_TOKEN"
echo "      - ADMIN_IDS"
echo "      - DATABASE_URL"
echo "      - WEBHOOK_HOST"
echo "      - SECRET_TOKEN"
echo "      - ENCRYPTION_KEY"
echo "   7. اضغط Deploy!"
echo ""
echo "📖 لمزيد من التفاصيل: README.md"
echo "=========================================="
