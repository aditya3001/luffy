import React from 'react';
import { Alert, Tag, Button, Space, Tooltip } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  WarningOutlined,
  InfoCircleOutlined,
  QuestionCircleOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { formatDistanceToNow } from 'date-fns';

interface TokenStatusProps {
  logSource: {
    id: string;
    name: string;
    code_indexing_enabled: boolean;
    token_status?: string;
    token_last_validated?: string;
    indexing_status?: string;
    indexing_error?: string;
    last_indexed_at?: string;
  };
  showDetails?: boolean;
}

export const TokenStatusBadge: React.FC<TokenStatusProps> = ({ logSource, showDetails = false }) => {
  const navigate = useNavigate();

  if (!logSource.code_indexing_enabled) {
    return <Tag>Code Indexing Disabled</Tag>;
  }

  const getStatusConfig = (status?: string) => {
    switch (status) {
      case 'valid':
        return {
          color: 'success',
          icon: <CheckCircleOutlined />,
          text: 'Valid',
          action: null,
        };
      case 'expired':
        return {
          color: 'error',
          icon: <CloseCircleOutlined />,
          text: 'Expired',
          action: 'Update Token',
        };
      case 'invalid':
        return {
          color: 'error',
          icon: <WarningOutlined />,
          text: 'Invalid',
          action: 'Update Token',
        };
      case 'not_configured':
        return {
          color: 'default',
          icon: <InfoCircleOutlined />,
          text: 'Not Configured',
          action: 'Configure',
        };
      default:
        return {
          color: 'default',
          icon: <QuestionCircleOutlined />,
          text: 'Unknown',
          action: 'Check Status',
        };
    }
  };

  const config = getStatusConfig(logSource.token_status);

  return (
    <Space direction="vertical" size="small" style={{ width: '100%' }}>
      <Space>
        <Tag color={config.color} icon={config.icon}>
          Token: {config.text}
        </Tag>

        {config.action && (
          <Button
            type="link"
            size="small"
            onClick={() => navigate(`/log-sources/${logSource.id}/edit`)}
          >
            {config.action}
          </Button>
        )}

        {logSource.token_last_validated && (
          <Tooltip
            title={`Last validated: ${new Date(
              logSource.token_last_validated
            ).toLocaleString()}`}
          >
            <InfoCircleOutlined style={{ color: '#999' }} />
          </Tooltip>
        )}
      </Space>

      {showDetails && logSource.last_indexed_at && (
        <Tag color="blue" icon={<CheckCircleOutlined />}>
          Last indexed: {formatDistanceToNow(new Date(logSource.last_indexed_at), { addSuffix: true })}
        </Tag>
      )}
    </Space>
  );
};

export const TokenExpiryAlert: React.FC<TokenStatusProps> = ({ logSource }) => {
  const navigate = useNavigate();

  if (!logSource.code_indexing_enabled) {
    return null;
  }

  if (logSource.token_status === 'expired' || logSource.token_status === 'invalid') {
    return (
      <Alert
        message="Access Token Expired"
        description={
          <Space direction="vertical" size="small">
            <div>
              The Git access token for <strong>{logSource.name}</strong> has expired or is invalid.
              Code indexing is currently disabled.
            </div>
            <div>
              Update your token to resume code indexing and enable enhanced RCA generation.
            </div>
          </Space>
        }
        type="error"
        showIcon
        closable
        action={
          <Button
            size="small"
            danger
            onClick={() => navigate(`/log-sources/${logSource.id}/edit`)}
          >
            Update Token
          </Button>
        }
        style={{ marginBottom: 16 }}
      />
    );
  }

  if (logSource.indexing_status === 'failed' && logSource.indexing_error) {
    return (
      <Alert
        message="Code Indexing Failed"
        description={
          <Space direction="vertical" size="small">
            <div>
              <strong>Error:</strong> {logSource.indexing_error}
            </div>
            {logSource.indexing_error.includes('token') && (
              <div>This may be due to an expired or invalid access token.</div>
            )}
          </Space>
        }
        type="warning"
        showIcon
        closable
        action={
          <Button
            size="small"
            onClick={() => navigate(`/log-sources/${logSource.id}/edit`)}
          >
            Check Configuration
          </Button>
        }
        style={{ marginBottom: 16 }}
      />
    );
  }

  return null;
};

export const TokenStatusCard: React.FC<TokenStatusProps> = ({ logSource }) => {
  const navigate = useNavigate();

  if (!logSource.code_indexing_enabled) {
    return (
      <Alert
        message="Code Indexing Disabled"
        description="Enable code indexing to get enhanced RCA with code context."
        type="info"
        showIcon
        action={
          <Button size="small" onClick={() => navigate(`/log-sources/${logSource.id}/edit`)}>
            Enable
          </Button>
        }
      />
    );
  }

  const isTokenValid = logSource.token_status === 'valid';
  const isIndexingHealthy = logSource.indexing_status !== 'failed';

  if (isTokenValid && isIndexingHealthy) {
    return (
      <Alert
        message="Code Indexing Active"
        description={
          <Space direction="vertical" size="small">
            <div>✅ Git token is valid</div>
            <div>✅ Code indexing is working</div>
            {logSource.last_indexed_at && (
              <div>
                Last indexed: {formatDistanceToNow(new Date(logSource.last_indexed_at), { addSuffix: true })}
              </div>
            )}
          </Space>
        }
        type="success"
        showIcon
      />
    );
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <TokenExpiryAlert logSource={logSource} />
    </Space>
  );
};
