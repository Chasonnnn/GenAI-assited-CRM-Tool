import { AlertCircleIcon } from 'lucide-react';

export const metadata = {
    title: 'Organization Not Found',
};

export default function OrgNotFoundPage() {
    return (
        <div className="min-h-screen flex items-center justify-center bg-background p-4">
            <div className="text-center max-w-md">
                <AlertCircleIcon className="size-16 mx-auto mb-6 text-muted-foreground/50" />
                <h1 className="text-2xl font-bold mb-4">
                    Organization Not Found
                </h1>
                <p className="text-muted-foreground mb-6">
                    The domain you&apos;re trying to access is not associated
                    with any organization. Please check the URL and try again.
                </p>
                <p className="text-sm text-muted-foreground">
                    If you believe this is an error, please contact your
                    organization administrator.
                </p>
            </div>
        </div>
    );
}
